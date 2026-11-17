"""Conjunto fictício da demonstração: 6 status x 4 prioridades x 6 prazos."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import sqlite3
from werkzeug.security import generate_password_hash
from database import sqlite_transaction

PREFIX='DEMO-FILTROS-'
SUBJECTS=(
    'Compra de materiais de escritório','Manutenção de impressora',
    'Liberação de acesso ao estoque','Correção da integração de compras',
    'Troca de equipamento de rede','Atualização de cadastro de fornecedor',
    'Instalação de software autorizado','Revisão de permissões do sistema',
    'Reposição de peças de manutenção','Ajuste no relatório de inventário',
    'Configuração de estação de trabalho','Conferência de pedidos internos')

def popular_demonstracao(app,password):
    """Acrescenta somente cenários ausentes, sem substituir dados ou edições existentes."""
    if not app.config.get('DEMONSTRACAO') or not app.config.get('AUTH_REQUIRED'):
        raise RuntimeError('A carga fictícia exige demonstração autenticada e banco separado.')
    with sqlite_transaction(app.config['DATABASE']) as db:
        db.row_factory=sqlite3.Row
        for role in ('gestor','colaborador','leitor'):
            email=role+'@example.test'
            if not db.execute('SELECT 1 FROM usuarios WHERE email=?',(email,)).fetchone():
                db.execute('INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES(?,?,?,?)',
                    (role.title()+' Demonstração',email,generate_password_hash(password),role))
        users={r['email']:r['id'] for r in db.execute('SELECT id,email FROM usuarios')}
        existing={r[0] for r in db.execute('SELECT titulo FROM demandas WHERE titulo LIKE ?',(PREFIX+'%',))}
    admin='admin@404.local'
    requesters=[users[email] for email in (admin,'gestor@example.test','colaborador@example.test','leitor@example.test')]
    assignees=[None,*requesters[:3]]
    today=app.config.get('REPORT_TODAY') or datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    statuses=('aberta','em_analise','em_andamento','aguardando','concluida','cancelada')
    priorities=('baixa','media','alta','critica')
    offsets=(-5,0,3,7,15,None)
    created=0
    with app.test_client() as client:
        client.get('/login')
        with client.session_transaction() as session:csrf=session['csrf_token']
        response=client.post('/login',data={'email':admin,'senha':password,'csrf_token':csrf})
        if response.status_code!=302:raise RuntimeError('Não foi possível autenticar a carga fictícia.')
        with client.session_transaction() as session:csrf=session['csrf_token']
        number=0
        for si,status in enumerate(statuses):
            for pi,priority in enumerate(priorities):
                for di,offset in enumerate(offsets):
                    number+=1
                    title=f'{PREFIX}{number:03d} | {SUBJECTS[(number-1)%len(SUBJECTS)]}'
                    if title in existing:continue
                    requester=requesters[(si+pi+di)%4]
                    responsible=assignees[(si*3+pi+di//2)%4]
                    deadline=(today+timedelta(days=offset)).isoformat() if offset is not None else ''
                    description=(f'DADOS FICTÍCIOS PARA TESTAR OS FILTROS DO SGDI.\n\n'
                        f'Cenário {number:03d} de 144: {SUBJECTS[(number-1)%len(SUBJECTS)]}.\n'
                        f'Status inicial: {status}. Prioridade: {priority}.\n'
                        'Registro para demonstração de cadastro, filtros combinados, paginação, CSV e relatórios. '
                        'Não contém informações reais de pessoas ou empresas.')
                    response=client.post('/demandas/nova',data={
                        'csrf_token':csrf,'titulo':title,'descricao':description,'solicitante_id':str(requester),
                        'responsavel_id':str(responsible) if responsible else '', 'status':status,
                        'prioridade':priority,'prazo':deadline})
                    if response.status_code!=302:raise RuntimeError(f'Falha ao criar o cenário fictício {number}.')
                    created+=1
        client.post('/logout',data={'csrf_token':csrf})
    ajustar_cronologia_demonstracao(app)
    return {'criadas':created,'previstas':144}

def ajustar_cronologia_demonstracao(app):
    """Distribui somente cenários fictícios intactos; não reescreve a auditoria."""
    if not app.config.get('DEMONSTRACAO') or not app.config.get('AUTH_REQUIRED'):
        raise RuntimeError('A cronologia fictícia exige demonstração autenticada.')
    today=app.config.get('REPORT_TODAY') or datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    changed=0
    with sqlite_transaction(app.config['DATABASE']) as db:
        rows=db.execute('SELECT id,titulo,status,prioridade,data_criacao,data_atualizacao,data_conclusao,descricao FROM demandas WHERE titulo LIKE ?', (PREFIX+'%',)).fetchall()
        for did,title,status,priority,created,updated,completed,description in rows:
            # Edições e datas já ajustadas são preservadas nas próximas execuções.
            if created!=updated or not description.startswith('DADOS FICTÍCIOS PARA TESTAR OS FILTROS DO SGDI.'):
                continue
            if status=='concluida' and completed!=created:
                continue
            try:number=int(title.split(' | ',1)[0][len(PREFIX):])
            except ValueError:continue
            if not 1<=number<=144:continue
            age=6+(number*7+number//6)%30
            conclusion=None
            if status=='concluida':
                duration=(1,3,5,10)[(number-1)%4]+(3 if priority=='critica' else 0)
                end=datetime.combine(today,datetime.min.time()).replace(hour=12)-timedelta(days=1+number%6)
                start=end-timedelta(days=duration)
                conclusion=end.isoformat(' ','seconds')
            else:
                start=datetime.combine(today,datetime.min.time()).replace(hour=9)-timedelta(days=age)
            db.execute('UPDATE demandas SET data_criacao=?,data_conclusao=? WHERE id=?',
                       (start.isoformat(' ','seconds'),conclusion,did))
            changed+=1
    return changed
