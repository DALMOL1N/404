import sqlite3
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from init_db import initialize_database


class SGDITestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "test.db"
        self.app = create_app({"TESTING":True,"AUTH_REQUIRED":True,"DATABASE":str(self.database),"SECRET_KEY":"test-secret","ADMIN_INITIAL_PASSWORD":"SenhaInicial!123","PER_PAGE":3})
        self.client = self.app.test_client()
        self.login()

    def tearDown(self): self.temp.cleanup()

    def token(self):
        self.client.get("/login")
        with self.client.session_transaction() as session: return session["csrf_token"]

    def post(self, path, data=None, **kwargs):
        form=dict(data or {}); form["csrf_token"]=self.token()
        return self.client.post(path,data=form,**kwargs)

    def login(self,email="admin@404.local",password="SenhaInicial!123"):
        return self.post("/login",{"email":email,"senha":password})

    def demand(self,title="Teste d'água"):
        response=self.post("/demandas/nova",{"titulo":title,"descricao":"Descrição com 'aspas'","solicitante_id":"1","status":"aberta","prioridade":"critica","prazo":"2030-12-31"})
        self.assertEqual(response.status_code,302)
        with sqlite3.connect(self.database) as db: return db.execute("SELECT id FROM demandas WHERE titulo=?",(title,)).fetchone()[0]

    def add_user(self,email,role):
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES (?,?,?,?)",(role.title(),email,generate_password_hash("SenhaUsuario!123"),role))

    def test_login_e_rotas_protegidas(self):
        self.post("/logout")
        for path in ("/","/demandas","/demandas/nova"):
            self.assertEqual(self.client.get(path).status_code,302)
        self.assertEqual(self.login(password="errada").status_code,200)
        self.assertEqual(self.login().status_code,302)

    def test_csrf_validacao_e_limite_de_conteudo(self):
        self.assertEqual(self.client.post("/demandas/nova",data={}).status_code,400)
        response=self.post("/demandas/nova",{"titulo":"","descricao":"x","solicitante":"","status":"x","prioridade":"x"})
        self.assertEqual(response.status_code,200); self.assertIn("obrigatório".encode(),response.data)
        self.assertEqual(self.client.post("/demandas/nova",data=b"x"*1_100_000,content_type="application/x-www-form-urlencoded").status_code,413)

    def test_criar_editar_comentar_historico_e_excluir_em_cascata(self):
        demand_id=self.demand()
        response=self.post(f"/demandas/{demand_id}/editar",{"titulo":"Título atualizado","descricao":"Nova descrição","solicitante_id":"1","status":"em_andamento","prioridade":"alta","prazo":"2030-11-30"})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.post(f"/demandas/{demand_id}/comentarios",{"comentario":"Em análise"}).status_code,302)
        page=self.client.get(f"/demandas/{demand_id}")
        self.assertIn("Título atualizado".encode(),page.data); self.assertIn("Demanda atualizada".encode(),page.data)
        self.assertEqual(self.client.get(f"/deletar/{demand_id}").status_code,405)
        self.assertEqual(self.post(f"/demandas/{demand_id}/excluir").status_code,302)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM comentarios WHERE demanda_id=?",(demand_id,)).fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM historico WHERE demanda_id=?",(demand_id,)).fetchone()[0],0)

    def test_busca_injecao_filtros_ordenacao_e_paginacao(self):
        for title in ("Bravo","Alfa","Charlie","Delta"): self.demand(title)
        response=self.client.get("/demandas?q=%27%20OR%201%3D1%20--")
        self.assertEqual(response.status_code,200); self.assertIn(b"Nenhuma demanda encontrada",response.data)
        response=self.client.get("/demandas?prioridade=critica&ordenar=titulo&pagina=2")
        self.assertEqual(response.status_code,200); self.assertIn(b"P\xc3\xa1gina 2 de 2",response.data)
        self.assertEqual(self.client.get("/demandas?ordenar=id);DROP%20TABLE%20demandas;--").status_code,200)
        with sqlite3.connect(self.database) as db: self.assertEqual(db.execute("SELECT COUNT(*) FROM demandas").fetchone()[0],4)

    def test_perfis_e_permissoes(self):
        demand_id=self.demand()
        for role in ("gestor","colaborador","leitor"): self.add_user(f"{role}@404.local",role)
        self.post("/logout"); self.login("leitor@404.local","SenhaUsuario!123")
        self.assertEqual(self.client.get(f"/demandas/{demand_id}").status_code,200)
        self.assertEqual(self.client.get("/demandas/nova").status_code,403)
        self.assertEqual(self.client.get(f"/demandas/{demand_id}/editar").status_code,403)
        self.assertEqual(self.post(f"/demandas/{demand_id}/comentarios",{"comentario":"x"}).status_code,403)
        self.post("/logout"); self.login("gestor@404.local","SenhaUsuario!123")
        self.assertEqual(self.client.get(f"/demandas/{demand_id}/editar").status_code,200)
        self.assertEqual(self.post(f"/demandas/{demand_id}/excluir").status_code,403)

    def test_usuarios_404_403_e_aliases_legados(self):
        response=self.post("/usuarios",{"nome":"Colaborador","email":"colaborador@404.local","senha":"SenhaUsuario!123","perfil":"colaborador"})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get("/detalhes/999999").status_code,404)
        self.assertEqual(self.client.get("/nova_demanda").status_code,200)


class MigrationTestCase(unittest.TestCase):
    def test_migracao_deduplica_remove_orfaos_e_cria_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            database=Path(temp)/"legacy.db"
            with sqlite3.connect(database) as db:
                db.executescript("""CREATE TABLE demandas(id INTEGER,titulo TEXT,descricao TEXT,solicitante TEXT,data_criacao TEXT);
                CREATE TABLE comentarios(id INTEGER,demanda_id INTEGER,comentario TEXT,autor TEXT,data TEXT);
                INSERT INTO demandas VALUES(3,'Demanda válida','Descrição válida','Maria','2024-01-01');
                INSERT INTO demandas VALUES(3,'Demanda válida','Descrição válida','Maria','2024-01-01');
                INSERT INTO demandas VALUES(NULL,'','Sem título','José','2024-01-02');
                INSERT INTO comentarios VALUES(1,3,'Comentário válido','Autor','2024-01-01');
                INSERT INTO comentarios VALUES(2,99,'Comentário órfão','Autor','2024-01-01');""")
            result=initialize_database(database,admin_password="SenhaInicial!123")
            self.assertEqual(result["demandas_importadas"],1); self.assertEqual(result["demandas_duplicadas"],1)
            self.assertEqual(result["demandas_invalidas"],1); self.assertEqual(result["comentarios_orfaos_ou_invalidos"],1)
            self.assertTrue(Path(result["backup"]).exists())
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM demandas").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM comentarios").fetchone()[0],1)
                self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
                self.assertEqual(db.execute("PRAGMA table_info(demandas)").fetchall()[0][5],1)

    def test_inicializacao_idempotente_e_senha_obrigatoria(self):
        with tempfile.TemporaryDirectory() as temp:
            database=Path(temp)/"new.db"
            with self.assertRaises(RuntimeError): initialize_database(database)
            initialize_database(database,admin_password="SenhaInicial!123")
            initialize_database(database,admin_password="ignorada")
            with sqlite3.connect(database) as db: self.assertEqual(db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0],1)


if __name__ == "__main__": unittest.main()
