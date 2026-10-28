from database import sqlite_transaction
import csv, io, sqlite3, tempfile, unittest
from datetime import date
from pathlib import Path
from app import create_app
from init_db import SCHEMA, initialize_database

class EmergencyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.db'
  self.app=create_app({'TESTING':True,'AUTH_REQUIRED':False,'DATABASE':str(self.path),'REPORT_TODAY':date(2026,10,7)})
  self.client=self.app.test_client()
  with sqlite_transaction(self.path) as db:
   self.person=db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES('Alice Teste','alice@example.test','unused','gestor')").lastrowid
   fixtures=[('Crítica vencida','aberta','critica',self.person,'2026-10-05',None),('=Crítica sem responsável','aberta','critica',None,'2026-10-05',None),('No prazo','aberta','media',self.person,'2026-10-08',None),('Crítica resolvida','concluida','critica',self.person,'2026-10-05','2026-10-05 00:00:00'),('Normal resolvida','concluida','media',self.person,'2026-10-02','2026-10-03 00:00:00'),('Cancelada','cancelada','critica',self.person,'2026-10-01',None),('Legado concluído','concluida','baixa',self.person,'2026-10-02',None)]
   for title,status,priority,person,deadline,finished in fixtures:
    db.execute("INSERT INTO demandas(titulo,descricao,solicitante,solicitante_id,status,prioridade,responsavel_id,prazo,data_criacao,data_conclusao) VALUES(?,?,?,1,?,?,?,?,?,?)",(title,'Descrição da demanda','Administrador',status,priority,person,deadline,'2026-10-01 00:00:00',finished))
 def tearDown(self): self.tmp.cleanup()
 def data(self,q=''):return self.client.get('/api/dashboard'+q).get_json()
 def test_contagens_percentuais_e_media(self):
  d=self.data();self.assertEqual((d['total'],d['abertas'],d['concluidas'],d['atrasadas']),(7,3,3,2));self.assertEqual(d['percentual_atrasadas'],28.6)
  self.assertEqual(d['media_dias'],3);self.assertAlmostEqual(d['media_ponderada_dias'],3.33);self.assertEqual(d['concluidas_sem_data'],1)
 def test_sla_exclui_sem_responsavel_canceladas_e_sem_data(self):
  d=self.data();self.assertEqual(d['sla_elegiveis'],4);self.assertEqual(d['sla_percentual'],50)
 def test_filtros_combinados_afetam_todos_indicadores(self):
  d=self.data(f'?inicio=2026-10-01&fim=2026-10-01&responsavel={self.person}&prioridade=critica&status=aberta')
  self.assertEqual(d['total'],1);self.assertEqual(d['atrasadas'],1);self.assertEqual(sum(x['total'] for x in d['por_status']),1);self.assertEqual(sum(x['total'] for x in d['evolucao']),1)
 def test_criticas_atrasadas_e_exportacao(self):
  d=self.data('?criticas_atrasadas=1');self.assertEqual(d['total'],2)
  response=self.client.get('/dashboard/exportar.csv');self.assertEqual(response.status_code,200)
  rows=list(csv.reader(io.StringIO(response.get_data(as_text=True).lstrip('\ufeff')),delimiter=';'))
  header=next(i for i,r in enumerate(rows) if r and r[0]=='ID'); exported=[]
  for row in rows[header+1:]:
   if not row:break
   exported.append(row)
  self.assertEqual(len(exported),2);self.assertEqual(exported[1][1],"'=Crítica sem responsável")
  self.assertIn('Filtros aplicados',response.get_data(as_text=True));self.assertIn('Equipe 404',response.get_data(as_text=True))
  filtered=self.client.get(f'/dashboard/exportar.csv?responsavel={self.person}').get_data(as_text=True);self.assertNotIn('Crítica sem responsável',filtered)
 def test_vazio_sem_divisao_por_zero(self):
  d=self.data('?inicio=2027-01-01');self.assertEqual(d['total'],0);self.assertIsNone(d['media_dias']);self.assertIsNone(d['sla_percentual']);self.assertEqual(d['percentual_abertas'],0)
 def test_filtros_invalidos_recusados(self):
  for q in ['inicio=abc','inicio=2026-10-08&fim=2026-10-01','status=xxx','responsavel=1;DROP','criticas_atrasadas=2']:
   self.assertEqual(self.client.get('/api/dashboard?'+q).status_code,400)
 def post_status(self,status):
  self.client.get('/')
  with self.client.session_transaction() as s:token=s['csrf_token']
  return self.client.post('/demandas/1/editar',data=dict(titulo='Crítica vencida',descricao='Descrição da demanda',solicitante_id='1',status=status,prioridade='critica',responsavel_id=str(self.person),prazo='2026-10-05',csrf_token=token))
 def test_conclusao_preservada_em_edicao_e_limpa_ao_reabrir(self):
  self.assertEqual(self.post_status('concluida').status_code,302)
  with sqlite_transaction(self.path) as db:first=db.execute('SELECT data_conclusao FROM demandas WHERE id=1').fetchone()[0]
  self.assertTrue(first);self.post_status('concluida')
  with sqlite_transaction(self.path) as db:self.assertEqual(db.execute('SELECT data_conclusao FROM demandas WHERE id=1').fetchone()[0],first)
  self.post_status('aberta')
  with sqlite_transaction(self.path) as db:self.assertIsNone(db.execute('SELECT data_conclusao FROM demandas WHERE id=1').fetchone()[0])
 def test_datas_inconsistentes_fora_da_media(self):
  with sqlite_transaction(self.path) as db:db.execute("UPDATE demandas SET data_conclusao='2025-01-01' WHERE id=4")
  d=self.data();self.assertEqual(d['media_dias'],2);self.assertEqual(d['concluidas_sem_data'],2)
 def test_migracao_backup_e_sem_datas_inventadas(self):
  path=Path(self.tmp.name)/'old.db'
  with sqlite_transaction(path) as db:db.executescript(SCHEMA.replace(' data_conclusao TEXT,',''))
  result=initialize_database(path,admin_password='SenhaTeste12345');self.assertTrue(Path(result['backup']).exists())
  self.assertIsNone(initialize_database(path,admin_password='SenhaTeste12345')['backup'])
