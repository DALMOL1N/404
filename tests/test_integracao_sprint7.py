"""Regressões da integração: demonstração isolada, filtros e preservação dos registros."""
import csv
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from app import create_app
from database import sqlite_transaction
from dados_demonstracao import popular_demonstracao

class IntegracaoSprint7Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'demonstracao.db'
        self.app=create_app(dict(TESTING=True,AUTH_REQUIRED=True,DEMONSTRACAO=True,DATABASE=str(self.path),
            SECRET_KEY='integracao-secret',ADMIN_INITIAL_PASSWORD='DemoSprint7!2026',REPORT_TODAY=date(2026,11,4)))

    def test_carga_exige_modo_demonstracao(self):
        self.app.config['DEMONSTRACAO']=False
        with self.assertRaises(RuntimeError):popular_demonstracao(self.app,'DemoSprint7!2026')
        with sqlite_transaction(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],0)

    def test_carga_completa_atribuicoes_historico_e_idempotencia(self):
        self.assertEqual(popular_demonstracao(self.app,'DemoSprint7!2026')['criadas'],144)
        self.assertEqual(popular_demonstracao(self.app,'DemoSprint7!2026')['criadas'],0)
        with sqlite_transaction(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],144)
            self.assertEqual(db.execute('SELECT COUNT(DISTINCT status),COUNT(DISTINCT prioridade) FROM demandas').fetchone(),(6,4))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas WHERE responsavel_id IS NULL').fetchone()[0],36)
            self.assertEqual(db.execute('SELECT COUNT(DISTINCT solicitante_id) FROM demandas').fetchone()[0],4)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM historico').fetchone()[0],144)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_carga_preserva_edicao_e_registro_preexistente(self):
        popular_demonstracao(self.app,'DemoSprint7!2026')
        with sqlite_transaction(self.path) as db:
            db.execute("UPDATE demandas SET descricao='Descrição editada durante o teste' WHERE id=1")
            db.execute("INSERT INTO demandas(titulo,descricao,solicitante,solicitante_id) VALUES('Registro anterior','Não deve ser removido','Administrador',1)")
        popular_demonstracao(self.app,'DemoSprint7!2026')
        with sqlite_transaction(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],145)
            self.assertEqual(db.execute('SELECT descricao FROM demandas WHERE id=1').fetchone()[0],'Descrição editada durante o teste')

    def test_filtro_de_prazo_combinado_e_csv_usam_o_mesmo_conjunto(self):
        popular_demonstracao(self.app,'DemoSprint7!2026')
        client=self.app.test_client();client.get('/login')
        with client.session_transaction() as session:csrf=session['csrf_token']
        client.post('/login',data={'csrf_token':csrf,'email':'admin@404.local','senha':'DemoSprint7!2026'})
        query='q=DEMO-FILTROS-&status=aberta&prioridade=critica&vencimento=proximos_7_dias'
        response=client.get('/demandas?'+query)
        self.assertEqual(response.status_code,200);self.assertIn('2 registros encontrados'.encode(),response.data)
        text=client.get('/demandas/exportar.csv?'+query).get_data(as_text=True).lstrip('\ufeff')
        rows=list(csv.reader(io.StringIO(text),delimiter=';'))
        start=next(i for i,r in enumerate(rows) if r and r[0]=='ID')+1
        result=[]
        for row in rows[start:]:
            if not row:break
            result.append(row)
        self.assertEqual(len(result),2)
        self.assertEqual({r[6] for r in result},{'2026-11-07','2026-11-11'})

    def test_api_nunca_herda_acesso_local_sem_bearer(self):
        local=create_app(dict(TESTING=True,AUTH_REQUIRED=False,DATABASE=str(Path(self.temp.name)/'local.db')))
        client=local.test_client();self.assertEqual(client.get('/').status_code,200)
        self.assertIn(client.get('/api/v1/demandas').status_code,(401,404))
        response=client.post('/api/v1/demandas',json={'titulo':'Teste','descricao':'Descrição válida','solicitante_id':1})
        self.assertIn(response.status_code,(400,401,404))
        with sqlite_transaction(local.config['DATABASE']) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],0)

if __name__=='__main__':unittest.main()
