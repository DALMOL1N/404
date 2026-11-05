"""Testes automatizados das funcionalidades da Sprint 6 (Exportação CSV e Ações Rápidas)."""
import csv
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from werkzeug.security import generate_password_hash

from app import create_app
from database import sqlite_transaction


class Sprint6Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "sprint6.db"
        self.app = create_app({
            "TESTING": True,
            "AUTH_REQUIRED": True,
            "DATABASE": str(self.database),
            "SECRET_KEY": "sprint6-secret-key",
            "ADMIN_INITIAL_PASSWORD": "SenhaInicial!123",
            "COMPANY_NAME": "Equipe 404",
        })
        self.client = self.app.test_client()
        self.login()

    def tearDown(self):
        self.temp.cleanup()

    def csrf_token(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def post(self, path, data=None, **kwargs):
        payload = dict(data or {})
        payload["csrf_token"] = self.csrf_token()
        return self.client.post(path, data=payload, **kwargs)

    def login(self, email="admin@404.local", password="SenhaInicial!123"):
        return self.post("/login", {"email": email, "senha": password})

    def criar_usuario(self, email, perfil, nome="Usuário Teste"):
        with sqlite_transaction(self.database) as db:
            cursor = db.execute(
                "INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES (?,?,?,?)",
                (nome, email, generate_password_hash("SenhaUsuario!123"), perfil),
            )
            return cursor.lastrowid

    def criar_demanda(self, titulo="Demanda Sprint 6", status="aberta", prioridade="alta", responsavel_id=""):
        response = self.post("/demandas/nova", {
            "titulo": titulo,
            "descricao": "Descrição detalhada para validação da Sprint 6.",
            "solicitante_id": "1",
            "status": status,
            "prioridade": prioridade,
            "responsavel_id": str(responsavel_id) if responsavel_id else "",
            "prazo": "2030-12-31",
        })
        self.assertEqual(response.status_code, 302)
        return int(response.location.split("/")[-1])

    def test_exportacao_csv_demandas_respeita_filtros_sanitiza_e_audita(self):
        self.criar_demanda(titulo="=Fórmula Perigosa", status="aberta", prioridade="critica")
        self.criar_demanda(titulo="Demanda Concluída", status="concluida", prioridade="baixa")

        response = self.client.get("/demandas/exportar.csv?status=aberta&prioridade=critica")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["Content-Type"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")

        conteudo = response.get_data(as_text=True).lstrip("\ufeff")
        linhas = list(csv.reader(io.StringIO(conteudo), delimiter=";"))
        indice_cabecalho = next(i for i, r in enumerate(linhas) if r and r[0] == "ID")
        exportadas = []
        for linha in linhas[indice_cabecalho + 1:]:
            if not linha:
                break
            exportadas.append(linha)

        self.assertEqual(len(exportadas), 1)
        self.assertEqual(exportadas[0][1], "'=Fórmula Perigosa")
        self.assertNotIn("Demanda Concluída", conteudo)

        with sqlite_transaction(self.database) as db:
            evento = db.execute(
                "SELECT recurso, detalhes_json FROM auditoria WHERE evento='relatorio.exportado' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(evento[0], "demandas")
            self.assertEqual(json.loads(evento[1])["quantidade"], 1)

    def test_exportacao_csv_rejeita_filtros_invalidos_e_exige_login(self):
        for query_invalida in ("status=invalido", "prioridade=invalida", "responsavel=abc", "solicitante=-5"):
            self.assertEqual(self.client.get("/demandas/exportar.csv?" + query_invalida).status_code, 400)
        self.post("/logout")
        self.assertEqual(self.client.get("/demandas/exportar.csv").status_code, 302)

    def test_atualizacao_rapida_de_status_por_colaborador_e_registro_conclusao(self):
        colaborador_id = self.criar_usuario("colab@404.local", "colaborador", nome="Colaborador Ágil")
        demanda_id = self.criar_demanda(responsavel_id=colaborador_id)

        self.post("/logout")
        self.login("colab@404.local", "SenhaUsuario!123")

        resposta = self.post(f"/demandas/{demanda_id}/status", {"status": "concluida"})
        self.assertEqual(resposta.status_code, 302)

        with sqlite_transaction(self.database) as db:
            status_atual, data_conclusao = db.execute(
                "SELECT status, data_conclusao FROM demandas WHERE id=?", (demanda_id,)
            ).fetchone()
            self.assertEqual(status_atual, "concluida")
            self.assertIsNotNone(data_conclusao)

            historico = db.execute(
                "SELECT acao, detalhes FROM historico WHERE demanda_id=? ORDER BY id DESC LIMIT 1", (demanda_id,)
            ).fetchone()
            self.assertEqual(historico[0], "Status atualizado rapidamente")
            self.assertIn("Aberta -> Concluída", historico[1])

            auditoria_json = db.execute(
                "SELECT detalhes_json FROM auditoria WHERE evento='demanda.alterada' AND recurso_id=? ORDER BY id DESC LIMIT 1",
                (demanda_id,),
            ).fetchone()[0]
            self.assertEqual(
                json.loads(auditoria_json)["alteracoes"]["status"],
                {"antes": "aberta", "depois": "concluida"},
            )

        # Reabertura limpa data_conclusao
        self.post(f"/demandas/{demanda_id}/status", {"status": "em_andamento"})
        with sqlite_transaction(self.database) as db:
            data_conclusao_reaberta = db.execute(
                "SELECT data_conclusao FROM demandas WHERE id=?", (demanda_id,)
            ).fetchone()[0]
            self.assertIsNone(data_conclusao_reaberta)

    def test_assumir_demanda_e_bloqueio_para_leitor(self):
        colaborador_id = self.criar_usuario("colab2@404.local", "colaborador", nome="Ana Colaboradora")
        self.criar_usuario("leitor@404.local", "leitor", nome="Leitor Teste")
        demanda_id = self.criar_demanda()

        self.post("/logout")
        self.login("colab2@404.local", "SenhaUsuario!123")
        resposta = self.post(f"/demandas/{demanda_id}/assumir")
        self.assertEqual(resposta.status_code, 302)

        with sqlite_transaction(self.database) as db:
            responsavel_atual = db.execute(
                "SELECT responsavel_id FROM demandas WHERE id=?", (demanda_id,)
            ).fetchone()[0]
            self.assertEqual(responsavel_atual, colaborador_id)

        self.post("/logout")
        self.login("leitor@404.local", "SenhaUsuario!123")
        self.assertEqual(self.post(f"/demandas/{demanda_id}/status", {"status": "concluida"}).status_code, 403)
        self.assertEqual(self.post(f"/demandas/{demanda_id}/assumir").status_code, 403)


if __name__ == "__main__":
    unittest.main()
