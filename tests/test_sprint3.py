import re,sqlite3,tempfile,unittest
from pathlib import Path
from html import unescape
from urllib.parse import urlsplit,parse_qs
from app import create_app
class Sprint3Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'test.db'
  self.app=create_app(dict(TESTING=True,AUTH_REQUIRED=False,DATABASE=str(self.db)));self.client=self.app.test_client()
  with sqlite3.connect(self.db) as db:
   self.resp=db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES('Bruno Teste','bruno@example.test','unused','colaborador')").lastrowid
   for i in range(63):db.execute("INSERT INTO demandas(titulo,descricao,solicitante,solicitante_id,status,prioridade,responsavel_id,data_criacao) VALUES(?,?,?,?,?,?,?,?)",(f'Demanda {i:03}','Descrição para testes','Administrador',1,'aberta' if i<32 else 'concluida','alta' if i<22 else 'baixa',self.resp if i<27 else None,'2026-09-22 10:00:00'))
 def tearDown(self):self.temp.cleanup()
 def post(self,path,form):
  self.client.get('/')
  with self.client.session_transaction() as s:token=s['csrf_token']
  return self.client.post(path,data={**form,'csrf_token':token})
 def ids(self,url):
  r=self.client.get(url);self.assertEqual(r.status_code,200)
  return [int(n) for n in re.findall(rb'<span class="id-badge">#(\d+)',r.data)]
 def test_acesso_direto_sem_login(self):
  for url in ['/','/demandas','/usuarios','/demandas/nova','/relatorios/solicitantes']:
   r=self.client.get(url);self.assertEqual(r.status_code,200);self.assertNotIn(b'aria-label="Sair"',r.data)
  self.assertEqual(self.client.get('/login').location,'/');self.assertNotIn(b'name="senha"',self.client.get('/usuarios').data)
 def test_filtros_individuais_e_combinados(self):
  for q,n in [('status=aberta',32),('prioridade=alta',22),(f'responsavel={self.resp}',27),('responsavel=sem',36),(f'status=aberta&prioridade=alta&responsavel={self.resp}',22)]:self.assertIn(f'{n} registros encontrados',self.client.get('/demandas?'+q).get_data(as_text=True))
 def test_paginas_sem_repeticao_nas_cinco_ordenacoes(self):
  for sort in ['recentes','antigas','prioridade','titulo','prazo']:
   ids=[]
   for p in range(1,8):ids+=self.ids(f'/demandas?ordenar={sort}&pagina={p}')
   self.assertEqual(len(ids),63);self.assertEqual(len(set(ids)),63)
 def test_tamanhos_e_limites(self):
  for n in [10,25,50]:self.assertEqual(len(self.ids(f'/demandas?por_pagina={n}')),n)
  for q in ['por_pagina=0','pagina=-2','pagina=abc']:self.assertEqual(self.ids('/demandas?'+q),self.ids('/demandas'))
  self.assertEqual(self.ids('/demandas?pagina=999'),self.ids('/demandas?pagina=7'))
 def test_links_preservam_filtros(self):
  q=f'q=Demanda&status=aberta&prioridade=alta&responsavel={self.resp}&solicitante=1&ordenar=titulo&por_pagina=10'
  body=self.client.get('/demandas?'+q).get_data(as_text=True)
  links=re.findall(r'href="([^"]+)" aria-label="Próxima página"',body);self.assertEqual(len(links),1)
  expected=parse_qs(q);expected['pagina']=['2'];self.assertEqual(parse_qs(urlsplit(unescape(links[0])).query),expected)
  for name in expected:self.assertIn(f'name="{name}"',body)
 def test_vazio_e_parametros_invalidos(self):
  self.assertIn(b'Nenhuma demanda encontrada',self.client.get('/demandas?q=inexistente').data)
  for q in ['status=xyz','prioridade=xyz','responsavel=1;DROP','solicitante=-1']:self.assertEqual(self.client.get('/demandas?'+q).status_code,400)
 def test_busca_curingas_literais(self):
  self.assertEqual(self.ids('/demandas?q=%25'),[]);self.assertEqual(self.ids('/demandas?q=_'),[])
 def test_cadastro_sem_senha_e_autoria_local(self):
  self.assertEqual(self.post('/usuarios',dict(nome='Carla Teste',email='carla@example.test',perfil='colaborador')).status_code,302)
  self.assertEqual(self.post('/demandas/nova',dict(titulo='Nova demanda local',descricao='Teste de cadastro sem login',solicitante_id='1',status='aberta',prioridade='media')).status_code,302)
  with sqlite3.connect(self.db) as db:
   actor=db.execute("SELECT criado_por_id FROM demandas WHERE titulo='Nova demanda local'").fetchone()[0];self.assertEqual(actor,self.app.config['LOCAL_ACTOR_ID']);self.assertEqual(db.execute('SELECT usuario_id FROM historico ORDER BY id DESC LIMIT 1').fetchone()[0],actor)
 def test_conta_local_nao_e_solicitante(self):
  r=self.post('/demandas/nova',dict(titulo='Inválida local',descricao='Teste solicitante inválido',solicitante_id=str(self.app.config['LOCAL_ACTOR_ID']),status='aberta',prioridade='media'));self.assertEqual(r.status_code,200)
  with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],63)
 def test_preserva_responsavel_inativo_na_edicao(self):
  with sqlite3.connect(self.db) as db:db.execute('UPDATE usuarios SET ativo=0 WHERE id=?',(self.resp,))
  r=self.post('/demandas/1/editar',dict(titulo='Demanda editada',descricao='Descrição atualizada',solicitante_id='1',responsavel_id=str(self.resp),status='aberta',prioridade='alta'));self.assertEqual(r.status_code,302)
  with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT responsavel_id FROM demandas WHERE id=1').fetchone()[0],self.resp)
 def test_csrf_sem_login(self):self.assertEqual(self.client.post('/demandas/1/excluir').status_code,400)
 def test_inicializacao_idempotente(self):
  again=create_app(dict(TESTING=True,AUTH_REQUIRED=False,DATABASE=str(self.db)));self.assertEqual(again.config['LOCAL_ACTOR_ID'],self.app.config['LOCAL_ACTOR_ID'])
