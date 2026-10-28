import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_app
from app import create_app
from init_db import initialize_database

class RequesterTests(unittest.TestCase):
    setUp = test_app.SGDITestCase.setUp
    tearDown = test_app.SGDITestCase.tearDown
    token = test_app.SGDITestCase.token
    post = test_app.SGDITestCase.post
    login = test_app.SGDITestCase.login
    add_user = test_app.SGDITestCase.add_user
    demand = test_app.SGDITestCase.demand

    def form(self, requester='1', **changes):
        form=dict(titulo='Demanda teste', descricao='Descrição válida',solicitante_id=requester,status='aberta',prioridade='alta',responsavel_id='')
        form.update(changes)
        return form

    def test_solicitante_obrigatorio_inexistente_inativo_e_id_malformado(self):
        self.add_user('inativo@teste.local','leitor')
        with sqlite3.connect(self.database) as db: db.execute('UPDATE usuarios SET ativo=0 WHERE id=2')
        for requester in ('','99999','2','abc','²','9'*200):
            response=self.post('/demandas/nova',self.form(requester))
            self.assertEqual(response.status_code,200)
            self.assertIn('Selecione um solicitante'.encode(), response.data)
        with sqlite3.connect(self.database) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0],0)

    def test_cadastro_vincula_id_e_ignora_nome_livre(self):
        response=self.post('/demandas/nova',self.form(solicitante='Nome adulterado'))
        self.assertEqual(response.status_code,302)
        with sqlite3.connect(self.database) as db:
            row=db.execute('SELECT solicitante_id,solicitante FROM demandas').fetchone()
            self.assertEqual(row,(1,'Administrador'))

    def test_homonimos_filtro_combinado_e_paginacao(self):
        self.add_user('pessoa2@teste.local','leitor')
        with sqlite3.connect(self.database) as db:db.execute("UPDATE usuarios SET nome='Mesmo Nome'")
        for n in range(4):self.post('/demandas/nova',self.form('1',titulo=f'Solicitante um {n}'))
        self.post('/demandas/nova',self.form('2',titulo='Somente outro solicitante'))
        page=self.client.get('/demandas?solicitante=1&prioridade=alta&pagina=1').data.decode()
        self.assertIn('solicitante=1',page);self.assertIn('Página 1 de 2',page)
        self.assertNotIn('Somente outro solicitante',page)
        page=self.client.get('/demandas?solicitante=2').data.decode()
        self.assertIn('Somente outro solicitante',page);self.assertNotIn('Solicitante um',page)
        self.assertEqual(self.client.get('/demandas?solicitante=9'+'9'*100).status_code,400)

    def test_relatorio_conta_status_e_usuarios_sem_demanda(self):
        self.add_user('zero@teste.local','leitor')
        for status in ('aberta','em_analise','em_andamento','aguardando','concluida','cancelada'):
            self.post('/demandas/nova',self.form(status=status))
        with patch('app.render_template',return_value='ok') as render:
            self.assertEqual(self.client.get('/relatorios/solicitantes').status_code,200)
            rows=render.call_args.kwargs['registros']
            first=next(x for x in rows if x['id']==1)
            self.assertEqual(tuple(first[k] for k in ('total','abertas','em_aberto','concluidas','canceladas')),(6,1,4,1,1))
            self.assertEqual(next(x for x in rows if x['id']==2)['total'],0)

    def test_troca_solicitante_registra_ids_e_atualiza_contagem(self):
        demand=self.demand();self.add_user('novo@teste.local','leitor')
        self.assertEqual(self.post(f'/demandas/{demand}/editar',self.form('2')).status_code,302)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT solicitante_id FROM demandas').fetchone()[0],2)
            self.assertIn('1 -> 2',db.execute("SELECT detalhes FROM historico WHERE acao='Demanda atualizada'").fetchone()[0])

    def test_inativo_preserva_historico_mas_nao_recebe_nova_demanda(self):
        self.add_user('pessoa@teste.local','leitor')
        self.post('/demandas/nova',self.form('2'))
        with sqlite3.connect(self.database) as db:db.execute('UPDATE usuarios SET ativo=0 WHERE id=2')
        page=self.client.get('/demandas/1/editar').data.decode();self.assertIn('(inativo)',page)
        self.assertEqual(self.post('/demandas/1/editar',self.form('2')).status_code,302)
        self.assertEqual(self.post('/demandas/nova',self.form('2')).status_code,200)
        self.assertIn('pessoa@teste.local',self.client.get('/relatorios/solicitantes').data.decode())

    def test_renomear_usuario_atualiza_consulta_sem_perder_vinculo(self):
        demand=self.demand()
        with sqlite3.connect(self.database) as db:db.execute("UPDATE usuarios SET nome='Nome atualizado' WHERE id=1")
        self.assertIn('Nome atualizado',self.client.get(f'/demandas/{demand}').data.decode())
        self.assertIn('1 registro',self.client.get('/demandas?q=Nome+atualizado').data.decode())

    def test_chave_estrangeira_bloqueia_orfao_e_exclusao_usuario_vinculado(self):
        demand=self.demand()
        with sqlite3.connect(self.database) as db:
            db.execute('PRAGMA foreign_keys=ON')
            with self.assertRaises(sqlite3.IntegrityError):db.execute('UPDATE demandas SET solicitante_id=999 WHERE id=?',(demand,))
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM usuarios WHERE id=1')
            with self.assertRaises(sqlite3.IntegrityError):db.execute('UPDATE demandas SET solicitante_id=NULL WHERE id=?',(demand,))

    def test_erro_validacao_preserva_remocao_responsavel(self):
        demand=self.demand()
        with sqlite3.connect(self.database) as db:db.execute('UPDATE demandas SET responsavel_id=1')
        page=self.post(f'/demandas/{demand}/editar',self.form(titulo='',responsavel_id='')).data.decode()
        from html.parser import HTMLParser
        class SelectParser(HTMLParser):
            active=False; selected=[]
            def handle_starttag(inner,tag,attrs):
                a=dict(attrs)
                if tag=='select':inner.active=a.get('id')=='responsavel_id'
                if tag=='option' and inner.active and 'selected' in a:inner.selected.append(a['value'])
            def handle_endtag(inner,tag):
                if tag=='select':inner.active=False
        parser=SelectParser();parser.feed(page);self.assertNotIn('1',parser.selected)
        self.assertEqual(self.post(f'/demandas/{demand}/editar',self.form()).status_code,302)
        with sqlite3.connect(self.database) as db:self.assertIsNone(db.execute('SELECT responsavel_id FROM demandas').fetchone()[0])

    def test_relatorio_e_rotas_respeitam_autenticacao_e_perfis(self):
        self.add_user('leitor@teste.local','leitor');self.post('/logout')
        self.assertEqual(self.client.get('/relatorios/solicitantes').status_code,302)
        self.login('leitor@teste.local','SenhaUsuario!123')
        self.assertEqual(self.client.get('/relatorios/solicitantes').status_code,200)
        self.assertEqual(self.post('/demandas/nova',self.form()).status_code,403)

class UpgradeTests(unittest.TestCase):
    def test_migracao_v2_preserva_todos_registros_e_pendencias_sem_adivinhar(self):
        # Use the actual previous schema to test the non-destructive v2 upgrade.
        old_source=Path(__file__).with_name('schema_v2.sql').read_text()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'v2.db'
            with sqlite3.connect(path) as db:
                db.executescript(old_source)
                db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES('Maria','maria@teste.local','hash','administrador')")
                db.execute("INSERT INTO demandas(titulo,descricao,solicitante) VALUES('Legado','Descrição antiga','Maria')")
                db.execute("INSERT INTO comentarios(demanda_id,comentario,autor) VALUES(1,'Preservar','Maria')")
                db.execute("INSERT INTO historico(demanda_id,acao) VALUES(1,'Histórico anterior')")
            result=initialize_database(path)
            self.assertTrue(Path(result['backup']).exists());self.assertEqual(result['solicitantes_pendentes'],1)
            self.assertIsNone(initialize_database(path)['backup'])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT solicitante,solicitante_id FROM demandas').fetchone(),('Maria',None))
                self.assertEqual(db.execute('SELECT COUNT(*) FROM comentarios').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM historico').fetchone()[0],1)
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            app=create_app(dict(TESTING=True,AUTH_REQUIRED=True,DATABASE=str(path),SECRET_KEY='migration-test'))
            client=app.test_client()
            with client.session_transaction() as session:session['usuario_id']=1;session['csrf_token']='test'
            self.assertIn('Vínculo pendente'.encode(),client.get('/demandas?solicitante=pendente').data)
            response=client.post('/demandas/1/editar',data=dict(csrf_token='test',titulo='Legado',descricao='Descrição antiga',solicitante_id='1',status='aberta',prioridade='media'))
            self.assertEqual(response.status_code,302)
            with sqlite3.connect(path) as db:self.assertEqual(db.execute('SELECT solicitante_id FROM demandas').fetchone()[0],1)
