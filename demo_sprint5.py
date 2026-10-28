"""Demonstração local autenticada. Contas e ações inteiramente fictícias."""
from database import sqlite_transaction
import secrets
import sqlite3
from pathlib import Path
from app import create_app

PASSWORD='DemoSprint5!2026'  # Conta pública de demonstração, nunca usar com dados reais.
path=Path(__file__).resolve().with_name('demonstracao-sprint5.db')
app=create_app(dict(AUTH_REQUIRED=True,DATABASE=str(path),SECRET_KEY=secrets.token_hex(32),ADMIN_INITIAL_PASSWORD=PASSWORD,COMPANY_NAME='Equipe 404 · Demonstração Sprint 05'))
with sqlite_transaction(path) as db:
    seeded=db.execute("SELECT 1 FROM demandas WHERE titulo='Auditoria da solicitação de compra'").fetchone()
if not seeded:
    client=app.test_client()
    def post(url,**data):
        client.get('/login')
        with client.session_transaction() as session:data['csrf_token']=session['csrf_token']
        response=client.post(url,data=data)
        if response.status_code>=400:raise RuntimeError('Falha ao criar demonstração')
        return response
    post('/login',email='admin@404.local',senha='tentativa-ficticia-incorreta')
    post('/login',email='admin@404.local',senha=PASSWORD)
    for role,email in [('gestor','gestor@example.test'),('leitor','leitor@example.test')]:
        with sqlite_transaction(path) as db:exists=db.execute('SELECT 1 FROM usuarios WHERE email=?',(email,)).fetchone()
        if not exists:post('/usuarios',nome=role.title()+' Demonstração',email=email,senha=PASSWORD,perfil=role)
    form=dict(titulo='Auditoria da solicitação de compra',descricao='Demanda fictícia para demonstrar rastreabilidade.',solicitante_id='1',status='aberta',prioridade='alta',prazo='2026-12-20')
    response=post('/demandas/nova',**form);did=int(response.location.split('/')[-1])
    form.update(status='em_andamento',responsavel_id='1');post(f'/demandas/{did}/editar',**form)
    post(f'/demandas/{did}/comentarios',comentario='Comentário fictício cujo texto não é copiado para auditoria.')
    deleted=post('/demandas/nova',**{**form,'titulo':'Demanda fictícia para exclusão'});removed=int(deleted.location.split('/')[-1]);post(f'/demandas/{removed}/excluir')
    post('/logout');post('/login',email='leitor@example.test',senha=PASSWORD)
    client.get('/auditoria')  # Recusa real ao perfil leitor.
    post('/logout')
if __name__=='__main__':
    print('Demonstração fictícia: admin@404.local / DemoSprint5!2026')
    app.run(host='127.0.0.1',port=5056,debug=False)
