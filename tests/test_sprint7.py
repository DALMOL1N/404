"""Integração real Flask + SQLite temporário: contrato, autorização e atomicidade."""
import csv
import io
import json
import sqlite3
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import create_app
from database import sqlite_transaction
from init_db import initialize_database

class Sprint7Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'api.db'
  self.config=dict(TESTING=True,AUTH_REQUIRED=False,DATABASE=str(self.path),SECRET_KEY='test-api-secret',ADMIN_INITIAL_PASSWORD='SenhaInicial!123',REPORT_TODAY=date(2026,11,3))
  self.app=create_app(self.config);self.client=self.app.test_client()
  with sqlite_transaction(self.path) as db:
   for name,role in [('Gestor','gestor'),('Colaborador','colaborador'),('Leitor','leitor')]:
    db.execute('INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES(?,?,?,?)',(name,role+'@example.test',generate_password_hash('SenhaTeste!123'),role))
  self.headers=self.auth()
 def auth(self,email='admin@404.local',password='SenhaInicial!123'):
  r=self.client.post('/api/v1/auth/token',json={'email':email,'senha':password})
  self.assertEqual(r.status_code,200,r.get_json())
  return {'Authorization':'Bearer '+r.json['data']['access_token']}
 def body(self,**updates):
  return dict(titulo='Demanda integrada',descricao='Criada por sistema externo de teste.',solicitante_id=1,prioridade='alta',**updates)
 def create(self,headers=None,body=None):
  r=self.client.post('/api/v1/demandas',headers=headers or self.headers,json=body or self.body())
  self.assertEqual(r.status_code,201,r.json);return r
 def count(self,table):
  with sqlite_transaction(self.path) as db:return db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
 def test_api_exige_token_mesmo_com_interface_local_ou_sessao(self):
  self.assertEqual(self.client.get('/').status_code,200)
  with self.client.session_transaction() as s:s['usuario_id']=1
  for headers in ({},{'Authorization':'Bearer errado'},{'Authorization':'Basic segredo'}):
   r=self.client.get('/api/v1/demandas',headers=headers)
   self.assertEqual(r.status_code,401);self.assertTrue(r.is_json);self.assertIn('Bearer',r.headers['WWW-Authenticate'])
  self.assertNotIn('Set-Cookie',self.client.get('/api/v1/demandas',headers=self.headers).headers)
 def test_token_hash_expiracao_e_revogacao(self):
  raw=self.headers['Authorization'].split()[1]
  with sqlite_transaction(self.path) as db:
   row=db.execute('SELECT token_hash,expira_em,criado_em FROM api_tokens').fetchone()
   self.assertNotEqual(row[0],raw);self.assertEqual(row[1]-row[2],3600)
  self.assertEqual(self.client.delete('/api/v1/auth/token',headers=self.headers).status_code,204)
  self.assertEqual(self.client.get('/api/v1/demandas',headers=self.headers).status_code,401)
  h=self.auth()
  with sqlite_transaction(self.path) as db:db.execute('UPDATE api_tokens SET expira_em=0')
  self.assertEqual(self.client.get('/api/v1/demandas',headers=h).status_code,401)
 def test_conta_inativa_senha_ou_perfil_atualizados_afetam_token(self):
  h=self.auth('gestor@example.test','SenhaTeste!123');did=self.create().json['data']['id']
  with sqlite_transaction(self.path) as db:db.execute("UPDATE usuarios SET perfil='leitor' WHERE email='gestor@example.test'")
  self.assertEqual(self.client.patch(f'/api/v1/demandas/{did}',json={'status':'concluida'},headers=h).status_code,403)
  with sqlite_transaction(self.path) as db:db.execute("UPDATE usuarios SET ativo=0 WHERE email='gestor@example.test'")
  self.assertEqual(self.client.get('/api/v1/demandas',headers=h).status_code,401)
  with sqlite_transaction(self.path) as db:db.execute("UPDATE usuarios SET ativo=1,senha_hash=? WHERE email='gestor@example.test'",(generate_password_hash('OutraSenha!123'),))
  self.assertEqual(self.client.get('/api/v1/demandas',headers=h).status_code,401)
 def test_ciclo_crud_completion_e_auditoria_atribuida(self):
  r=self.create();did=r.json['data']['id'];self.assertEqual(r.headers['Location'],f'/api/v1/demandas/{did}')
  r=self.client.patch(r.headers['Location'],json={'status':'concluida','prazo':'2026-11-20'},headers=self.headers)
  self.assertEqual(r.status_code,200);self.assertIsNotNone(r.json['data']['data_conclusao'])
  r=self.client.patch(f'/api/v1/demandas/{did}',json={'status':'em_andamento'},headers=self.headers)
  self.assertIsNone(r.json['data']['data_conclusao'])
  self.assertEqual(self.client.delete(f'/api/v1/demandas/{did}',headers=self.headers).status_code,204)
  self.assertEqual(self.client.get(f'/api/v1/demandas/{did}',headers=self.headers).status_code,404)
  with sqlite_transaction(self.path) as db:
   events=db.execute("SELECT usuario_id,identidade,detalhes_json FROM auditoria WHERE recurso_id=? AND recurso='demanda'",(did,)).fetchall()
   self.assertEqual(len(events),4)
   for uid,identity,details in events:
    self.assertEqual(uid,1);self.assertEqual(identity,'autenticada');self.assertIn('/api/v1/demandas',details)
    self.assertNotIn('Criada por sistema',details);self.assertNotIn('Bearer',details)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM historico WHERE demanda_id=?',(did,)).fetchone()[0],0)
 def test_matriz_de_perfis(self):
  did=self.create().json['data']['id']
  for role,create_status,patch_status,delete_status in [('gestor',201,200,403),('colaborador',201,403,403),('leitor',403,403,403)]:
   with self.subTest(role=role):
    h=self.auth(role+'@example.test','SenhaTeste!123')
    self.assertEqual(self.client.get('/api/v1/demandas',headers=h).status_code,200)
    self.assertEqual(self.client.post('/api/v1/demandas',headers=h,json=self.body()).status_code,create_status)
    self.assertEqual(self.client.patch(f'/api/v1/demandas/{did}',headers=h,json={'status':'em_analise'}).status_code,patch_status)
    self.assertEqual(self.client.delete(f'/api/v1/demandas/{did}',headers=h).status_code,delete_status)
 def test_campos_invalidos_nao_gravam(self):
  before=self.count('demandas')
  for changes in [{'titulo':'x'},{'descricao':None},{'solicitante_id':True},{'solicitante_id':'1'},{'solicitante_id':10**25},{'status':[]},{'prioridade':'super'},{'prazo':'2026-02-30'},{'prazo':'20261103'},{'responsavel_id':False},{'criado_por_id':9},{'id':999}]:
   with self.subTest(changes=changes):
    r=self.client.post('/api/v1/demandas',headers=self.headers,json={**self.body(),**changes})
    self.assertEqual(r.status_code,422,r.json);self.assertIn('fields',r.json['error'])
  self.assertEqual(self.count('demandas'),before)
 def test_usuario_tecnico_inativo_e_responsavel_leitor_recusados(self):
  with sqlite_transaction(self.path) as db:
   local=self.app.config['LOCAL_ACTOR_ID'];reader=db.execute("SELECT id FROM usuarios WHERE perfil='leitor'").fetchone()[0]
   inactive=db.execute("SELECT id FROM usuarios WHERE perfil='gestor'").fetchone()[0];db.execute('UPDATE usuarios SET ativo=0 WHERE id=?',(inactive,))
  for changes in [{'solicitante_id':local},{'solicitante_id':inactive},{'responsavel_id':reader},{'responsavel_id':99999}]:
   self.assertEqual(self.client.post('/api/v1/demandas',headers=self.headers,json={**self.body(),**changes}).status_code,422)
 def test_patch_preserva_vinculos_inativos_e_campos_nao_enviados(self):
  with sqlite_transaction(self.path) as db:user=db.execute("SELECT id FROM usuarios WHERE perfil='gestor'").fetchone()[0]
  did=self.create(body={**self.body(),'responsavel_id':user,'solicitante_id':user}).json['data']['id']
  with sqlite_transaction(self.path) as db:db.execute('UPDATE usuarios SET ativo=0 WHERE id=?',(user,))
  r=self.client.patch(f'/api/v1/demandas/{did}',headers=self.headers,json={'status':'aguardando'})
  self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['data']['responsavel_id'],user);self.assertEqual(r.json['data']['titulo'],'Demanda integrada')
 def test_json_formato_vazio_campos_desconhecidos_e_metodos(self):
  for body in [[],None,42,'texto']:
   r=self.client.post('/api/v1/demandas',data=json.dumps(body),content_type='application/json',headers=self.headers)
   self.assertEqual(r.status_code,400,r.data)
  self.assertEqual(self.client.post('/api/v1/demandas',data='{',content_type='application/json',headers=self.headers).status_code,400)
  self.assertEqual(self.client.post('/api/v1/demandas',data='a=1',headers=self.headers).status_code,415)
  did=self.create().json['data']['id']
  self.assertEqual(self.client.patch(f'/api/v1/demandas/{did}',json={},headers=self.headers).status_code,422)
  for path,method,code in [('/api/v1/demandas/999999999999999999999999999999999999','get',404),('/api/v1/nao-existe','get',404),('/api/v1/demandas','put',405)]:
   r=getattr(self.client,method)(path,headers=self.headers);self.assertEqual(r.status_code,code);self.assertTrue(r.is_json)
 def test_limite_conteudo_sem_html_ou_segredos(self):
  r=self.client.post('/api/v1/demandas',headers=self.headers,data='x'*1_100_000,content_type='application/json')
  self.assertEqual(r.status_code,413);self.assertTrue(r.is_json)
  self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')
 def test_busca_injecao_e_parametros_invalidos(self):
  self.create()
  for query in ["q=%27%20OR%201=1--",'q=%25','q=%5F']:
   r=self.client.get('/api/v1/demandas?'+query,headers=self.headers);self.assertEqual(r.status_code,200);self.assertEqual(r.json['meta']['total'],0)
  for query in ['pagina=0','pagina=x','por_pagina=1000','ordenar=SQL','status=x','prioridade=x','responsavel=SQL','solicitante=-1','vencimento=SQL','desconhecido=1','status=aberta&status=concluida']:
   with self.subTest(query=query):self.assertEqual(self.client.get('/api/v1/demandas?'+query,headers=self.headers).status_code,400)
 def test_paginacao_filtros_e_mesmo_resultado_no_csv_e_tela(self):
  for i in range(12):self.create(body={**self.body(),'titulo':f'Filtrada {i:02}','prazo':'2026-11-02'})
  self.create(body={**self.body(),'titulo':'Encerrada','prazo':'2026-11-02','status':'concluida'})
  query='vencimento=atrasadas&prioridade=alta&ordenar=titulo&por_pagina=10'
  first=self.client.get('/api/v1/demandas?'+query,headers=self.headers).json
  second=self.client.get('/api/v1/demandas?'+query+'&pagina=2',headers=self.headers).json
  self.assertEqual(first['meta']['total'],12);self.assertEqual(len(first['data']),10);self.assertEqual(len(second['data']),2)
  self.assertFalse(set(x['id'] for x in first['data'])&set(x['id'] for x in second['data']))
  text=self.client.get('/demandas/exportar.csv?'+query).get_data(as_text=True)
  self.assertIn('Quantidade;12',text);self.assertNotIn('Encerrada',text)
  page=self.client.get('/demandas?'+query).get_data(as_text=True)
  self.assertIn('de 12',page);self.assertIn('vencimento=atrasadas',page)
 def test_usuarios_retorna_somente_id_nome_sem_conta_local(self):
  r=self.client.get('/api/v1/usuarios',headers=self.headers)
  self.assertEqual(r.status_code,200)
  for user in r.json['data']:self.assertEqual(set(user),{'id','nome'});self.assertNotEqual(user['id'],self.app.config['LOCAL_ACTOR_ID'])
  self.assertEqual(r.json['meta']['total'],4)
  self.assertEqual(self.client.get('/api/v1/usuarios?tipo=responsaveis',headers=self.headers).json['meta']['total'],3)
 def test_respostas_e_logs_nao_expoem_hash_email_token_ou_query(self):
  did=self.create().json['data']['id']
  r=self.client.get(f'/api/v1/demandas/{did}',headers=self.headers)
  for key in ['senha_hash','email','token_hash','solicitante_email','solicitante']:self.assertNotIn(key,r.json['data'])
  self.client.get('/api/v1/demandas?q=segredo-do-cliente',headers=self.headers)
  with sqlite_transaction(self.path) as db:logs='\n'.join(row[0] for row in db.execute('SELECT detalhes_json FROM auditoria'))
  for secret in ['segredo-do-cliente',self.headers['Authorization'].split()[1],'SenhaInicial!123']:self.assertNotIn(secret,logs)
 def test_protecao_csrf_html_nao_e_enfraquecida_pelo_bearer(self):
  self.assertEqual(self.client.post('/demandas/nova',json=self.body(),headers=self.headers).status_code,400)
  self.assertEqual(self.client.post('/api/v1/demandas',json=self.body(),headers=self.headers).status_code,201)
 def test_https_obrigatorio_fora_de_loopback(self):
  for host,remote in [('http://192.168.1.10','192.168.1.5'),('http://exemplo.test','127.0.0.1')]:
   r=self.client.get('/api/v1/demandas',base_url=host,environ_overrides={'REMOTE_ADDR':remote},headers=self.headers)
   self.assertEqual(r.status_code,426)
  r=self.client.get('/api/v1/demandas',base_url='https://exemplo.test',headers=self.headers)
  self.assertEqual(r.status_code,200)
 def test_rate_limit_persistente_e_expiracao_de_janela(self):
  config={**self.config,'API_LOGIN_LIMIT':2};client=create_app(config).test_client()
  for expected in [401,401,429]:
   r=client.post('/api/v1/auth/token',json={'email':'naoexiste@example.test','senha':'errada'},environ_overrides={'REMOTE_ADDR':'127.0.0.2'})
   self.assertEqual(r.status_code,expected)
  self.assertIn('Retry-After',r.headers)
  with sqlite_transaction(self.path) as db:db.execute('UPDATE api_login_limites SET reinicia_em=0')
  self.assertEqual(client.post('/api/v1/auth/token',json={'email':'naoexiste@example.test','senha':'errada'}).status_code,401)
 def test_falha_auditoria_impede_gravacao_da_demanda(self):
  before=self.count('demandas')
  with patch('api.record',side_effect=sqlite3.OperationalError('segredo-que-nao-pode-vazar')):
   r=self.client.post('/api/v1/demandas',json=self.body(),headers=self.headers)
  self.assertEqual(r.status_code,503);self.assertNotIn('segredo',r.get_data(as_text=True));self.assertEqual(self.count('demandas'),before)
 def test_openapi_documentacao_e_rotas_correspondem(self):
  r=self.client.get('/api/v1/openapi.json');self.assertEqual(r.status_code,200);self.assertEqual(r.json['openapi'],'3.0.3')
  implemented={(rule.rule.replace('<int:demanda_id>','{id}').removeprefix('/api/v1'),method.lower()) for rule in self.app.url_map.iter_rules() if rule.endpoint.startswith('api_v1.') for method in rule.methods-{'HEAD','OPTIONS'}}
  declared={(path,method) for path,ops in r.json['paths'].items() for method in ops if method!='parameters'}
  self.assertEqual(implemented,declared)
  self.assertEqual(self.client.get('/api/docs').status_code,200)
 def test_migracao_aditiva_tem_backup_idempotencia_e_integridade(self):
  did=self.create().json['data']['id']
  with sqlite_transaction(self.path) as db:db.execute('DROP TABLE api_tokens');db.execute('DROP TABLE api_login_limites')
  result=initialize_database(self.path)
  self.assertTrue(Path(result['backup']).is_file());self.assertEqual(self.count('demandas'),1)
  result=initialize_database(self.path);self.assertIsNone(result['backup'])
  with sqlite_transaction(self.path) as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
 def test_login_invalido_e_conta_tecnica_nao_geram_token(self):
  before=self.count('api_tokens')
  for email in ['admin@404.local','inexistente@example.test','operacao-local@sgdi.invalid']:
   r=self.client.post('/api/v1/auth/token',json={'email':email,'senha':'invalida'})
   self.assertEqual(r.status_code,401)
  self.assertEqual(self.count('api_tokens'),before)

 def test_proxy_so_e_confiavel_quando_configurado_e_producao_requer_login(self):
  import os
  with patch.dict(os.environ,{'APP_ENV':'production','SGDI_TRUST_PROXY':'0'}):
   with self.assertRaises(RuntimeError):create_app(self.config)
  with patch.dict(os.environ,{'SGDI_TRUST_PROXY':'0'}):
   client=create_app(self.config).test_client()
   r=client.get('/api/v1/demandas',base_url='http://api.example.test',headers={**self.headers,'X-Forwarded-Proto':'https'})
   self.assertEqual(r.status_code,426)
  with patch.dict(os.environ,{'SGDI_TRUST_PROXY':'1'}):
   client=create_app(self.config).test_client()
   r=client.get('/api/v1/demandas',base_url='http://api.example.test',headers={**self.headers,'X-Forwarded-Proto':'https'})
   self.assertEqual(r.status_code,200)

if __name__=='__main__':unittest.main()
