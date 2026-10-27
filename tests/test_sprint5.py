from database import sqlite_transaction
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from app import create_app
from init_db import initialize_database

class AuditTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'audit.db'
  self.app=create_app(dict(TESTING=True,AUTH_REQUIRED=True,DATABASE=str(self.path),SECRET_KEY='test',ADMIN_INITIAL_PASSWORD='SenhaInicial!123'))
  self.client=self.app.test_client();self.login()
 def tearDown(self):self.temp.cleanup()
 def post(self,path,**data):
  self.client.get('/login')
  with self.client.session_transaction() as s:data['csrf_token']=s['csrf_token']
  return self.client.post(path,data=data)
 def login(self,email='admin@404.local',password='SenhaInicial!123',**extra):return self.post('/login',email=email,senha=password,**extra)
 def rows(self,event=None):
  with sqlite_transaction(self.path) as db:
   db.row_factory=sqlite3.Row
   return [dict(r) for r in db.execute('SELECT * FROM auditoria'+(' WHERE evento=?' if event else '')+' ORDER BY id',(event,) if event else ())]
 def form(self,**extra):return dict(titulo='Título privado CPF fictício',descricao='Descrição pessoal confidencial',solicitante_id='1',status='aberta',prioridade='media',**extra)
 def demand(self):
  response=self.post('/demandas/nova',**self.form());self.assertEqual(response.status_code,302)
  return int(response.location.split('/')[-1])
 def test_autenticacao_sucesso_falha_logout_sem_segredos(self):
  self.post('/logout');r=self.login('pessoal@example.test','SenhaPrivadaNaoGuardar');self.assertEqual(r.status_code,200)
  failed=self.rows('autenticacao.falha')[-1]
  self.assertIsNone(failed['usuario_id']);self.assertEqual(failed['identidade'],'anonima')
  self.assertEqual(self.rows('autenticacao.sucesso')[0]['usuario_id'],1)
  serialized=json.dumps(self.rows());self.assertNotIn('SenhaPrivada',serialized);self.assertNotIn('pessoal@example',serialized)
  self.assertEqual(len(self.rows('sessao.encerrada')),1)
 def test_mudancas_e_request_id_sem_textos_pessoais(self):
  did=self.demand();form=self.form();form.update(status='concluida',titulo='Outro texto privado',responsavel_id='1')
  r=self.post(f'/demandas/{did}/editar',**form);event=self.rows('demanda.alterada')[-1]
  details=json.loads(event['detalhes_json'])['alteracoes']
  self.assertEqual(details['status'],{'antes':'aberta','depois':'concluida'})
  self.assertEqual(details['titulo'],{'alterado':True});self.assertEqual(event['request_id'],r.headers['X-Request-ID'])
  serialized=json.dumps(self.rows());self.assertNotIn('privado',serialized);self.assertNotIn('confidencial',serialized)
  self.assertEqual(event['recurso_id'],did)
 def test_comentario_nao_copia_corpo(self):
  did=self.demand();self.post(f'/demandas/{did}/comentarios',comentario='SEGREDO TEXTO LIVRE')
  self.assertEqual(self.rows('comentario.criado')[-1]['recurso_id'],did);self.assertNotIn('SEGREDO',json.dumps(self.rows()))
 def test_exclusao_preserva_auditoria(self):
  did=self.demand();self.post(f'/demandas/{did}/excluir')
  self.assertEqual(self.rows('demanda.excluida')[-1]['recurso_id'],did)
  self.assertEqual(self.rows('demanda.criada')[-1]['recurso_id'],did)
  with sqlite_transaction(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],0)
 def test_triggers_bloqueiam_edicao_e_exclusao(self):
  with sqlite_transaction(self.path) as db:
   for sql in ['UPDATE auditoria SET evento="falso"','DELETE FROM auditoria']:
    with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)
  self.assertEqual(len(self.rows()),1)
 def test_usuario_criacao_ativacao_sem_nome_email_senha(self):
  self.post('/usuarios',nome='Pessoa Privada',email='privada@example.test',senha='SenhaPrivada!123',perfil='leitor')
  uid=self.rows('usuario.criado')[-1]['recurso_id'];self.post(f'/usuarios/{uid}/alternar')
  event=self.rows('usuario.situacao_alterada')[-1];self.assertEqual(json.loads(event['detalhes_json'])['alteracoes']['ativo'],{'antes':1,'depois':0})
  serialized=json.dumps(self.rows());self.assertNotIn('Pessoa Privada',serialized);self.assertNotIn('privada@example',serialized);self.assertNotIn('SenhaPrivada',serialized)
 def test_permissoes_anonimo_leitor_gestor(self):
  for role in ('leitor','gestor'):
   self.post('/usuarios',nome=role,email=role+'@example.test',senha='SenhaUsuario!123',perfil=role)
  self.post('/logout');self.assertEqual(self.client.get('/auditoria').status_code,302)
  self.login('leitor@example.test','SenhaUsuario!123')
  self.assertEqual(self.client.get('/auditoria').status_code,403);self.assertEqual(self.client.get('/auditoria/exportar.json').status_code,403)
  self.assertTrue(self.rows('acesso.negado'));self.post('/logout');self.login('gestor@example.test','SenhaUsuario!123')
  self.assertEqual(self.client.get('/auditoria').status_code,200);self.assertEqual(self.client.get('/auditoria/exportar.json').status_code,200)
 def test_csrf_e_validacao_recusados_sem_dados(self):
  self.assertEqual(self.client.post('/demandas/nova',data={'descricao':'SEGREDO'}).status_code,400)
  self.assertTrue(self.rows('requisicao.recusada'))
  self.post('/demandas/nova',titulo='x',descricao='SEGREDO')
  self.assertTrue(self.rows('operacao.recusada'));self.assertNotIn('SEGREDO',json.dumps(self.rows()))
 def test_consulta_filtros_exportacao_e_sem_cache(self):
  did=self.demand();event=self.rows('demanda.criada')[-1]
  q=f"?evento=demanda.criada&usuario=1&resultado=sucesso&recurso_id={did}&request_id={event['request_id']}"
  r=self.client.get('/auditoria/exportar.json'+q);data=r.get_json()
  self.assertEqual(data['quantidade'],1);self.assertEqual(data['eventos'][0]['id'],event['id']);self.assertIn('detalhes',data['eventos'][0]);self.assertEqual(r.headers['Cache-Control'],'no-store')
  self.assertTrue(self.rows('auditoria.exportada'))
  self.assertEqual(self.client.get('/auditoria?evento=demanda.excluida').status_code,200);self.assertTrue(self.rows('auditoria.consultada'))
 def test_filtros_invalidos_e_injecao(self):
  for q in ['usuario=1%20OR%201=1','evento=xxx','inicio=2026-99-01','inicio=2026-10-20&fim=2026-10-01','pagina=abc','request_id=foo','resultado=sim','recurso_id=-1']:
   self.assertEqual(self.client.get('/auditoria?'+q).status_code,400,q)
 def test_transacao_reverte_negocio_se_log_falha(self):
  with sqlite_transaction(self.path) as db:db.executescript("CREATE TRIGGER simula_falha BEFORE INSERT ON auditoria WHEN NEW.evento='demanda.criada' BEGIN SELECT RAISE(ABORT,'simulada'); END;")
  with self.assertRaises(sqlite3.IntegrityError):self.demand()
  with sqlite_transaction(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],0)
 def test_redirect_rejeita_esquema_e_barras_invertidas(self):
  for target in ['https://externo.invalid','/\\externo.invalid','https:/externo.invalid','//externo.invalid']:
   self.post('/logout');self.assertEqual(self.login(proximo=target).location,'/')
 def test_modo_local_nao_afirma_identidade_pessoal(self):
  local=create_app(dict(TESTING=True,AUTH_REQUIRED=False,DATABASE=str(Path(self.temp.name)/'local.db')))
  c=local.test_client();c.get('/')
  with c.session_transaction() as s:token=s['csrf_token']
  c.post('/demandas/nova',data={**self.form(),'csrf_token':token})
  with sqlite_transaction(local.config['DATABASE']) as db:self.assertEqual(db.execute('SELECT identidade FROM auditoria').fetchone()[0],'local')
  self.assertIn('não uma pessoa'.encode(),c.get('/auditoria').data)
 def test_migracao_backup_idempotencia_preserva_legado(self):
  did=self.demand()
  with sqlite_transaction(self.path) as db:db.executescript('DROP TABLE auditoria;')
  result=initialize_database(self.path);self.assertTrue(Path(result['backup']).exists())
  self.assertIsNone(initialize_database(self.path)['backup'])
  with sqlite_transaction(self.path) as db:
   self.assertEqual(db.execute('SELECT id FROM demandas').fetchone()[0],did);self.assertEqual(db.execute('SELECT COUNT(*) FROM auditoria').fetchone()[0],0)
 def test_paginacao_e_limite_exportacao(self):
  for _ in range(28):self.client.get('/auditoria')
  self.assertIn('Página 2 de'.encode(),self.client.get('/auditoria?pagina=2').data)
  with sqlite_transaction(self.path) as db:
   db.executemany("INSERT INTO auditoria(instante,evento,resultado,identidade,recurso,request_id,detalhes_json) VALUES('2026-10-20T00:00:00+00:00','demanda.criada','sucesso','anonima','sistema',?,'{}')",[(f'{i:032x}',) for i in range(1001)])
  self.assertEqual(self.client.get('/auditoria/exportar.json').status_code,400)
 def test_falha_interna_registrada_sem_excecao(self):
  self.app.config['PROPAGATE_EXCEPTIONS']=False
  with sqlite_transaction(self.path) as db:db.executescript("CREATE TRIGGER simula_falha BEFORE INSERT ON demandas BEGIN SELECT RAISE(ABORT,'CONTEUDO_SIGILOSO'); END;")
  with self.assertLogs(self.app.logger,level='ERROR') as logged:r=self.post('/demandas/nova',**self.form())
  self.assertEqual(r.status_code,500);self.assertNotIn('CONTEUDO_SIGILOSO',' '.join(logged.output))
  self.assertTrue(self.rows('sistema.erro'));self.assertNotIn('CONTEUDO_SIGILOSO',json.dumps(self.rows()))

if __name__=='__main__':unittest.main()
