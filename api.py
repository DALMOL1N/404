"""API REST v1 independente da sessão da interface. Autorização por perfil atual."""
from datetime import date, datetime
from functools import wraps
from hashlib import sha256
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import json
import re
import secrets
import sqlite3
import time

from flask import Blueprint, abort, current_app, g, jsonify, make_response, render_template, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from auditoria import changes, record
from catalogo import STATUS, PRIORIDADES
from consultas import consultar, selecionar

FIELDS=('titulo','descricao','solicitante_id','status','prioridade','responsavel_id','prazo')
OUTPUT=(*FIELDS,'id','criado_por_id','data_criacao','data_atualizacao','data_conclusao')
ERRORS={400:('invalid_request','Requisição inválida.'),401:('unauthorized','Autenticação Bearer necessária ou token inválido.'),
        403:('forbidden','Seu perfil não tem permissão para esta operação.'),404:('not_found','Recurso não encontrado.'),
        405:('method_not_allowed','Método não permitido.'),409:('conflict','Conflito ao salvar os dados.'),
        413:('payload_too_large','Conteúdo excede o limite de 1 MB.'),415:('unsupported_media_type','Envie Content-Type application/json.'),
        422:('validation_error','Revise os campos enviados.'),426:('https_required','Utilize HTTPS para acessar a API fora deste computador.'),
        429:('rate_limited','Muitas tentativas. Aguarde antes de tentar novamente.'),500:('internal_error','Erro interno. Informe o identificador da requisição.'),
        503:('service_unavailable','Serviço temporariamente indisponível. Tente novamente.')}

def is_api_request():
    return request.path=='/api/v1' or request.path.startswith('/api/v1/')

def api_error_response(status,message=None,fields=None):
    code,default=ERRORS.get(status,('request_failed','A requisição não pôde ser concluída.'))
    error={'code':code,'message':message or default}
    if fields:error['fields']=fields
    response=make_response(jsonify(error=error,request_id=g.get('request_id','')),status)
    if status==401:response.headers['WWW-Authenticate']='Bearer realm="sgdi-api"'
    return response

class ValidationError(Exception):
    def __init__(self,fields):self.fields=fields

def payload():
    if not request.is_json:abort(415)
    body=request.get_json()
    if not isinstance(body,dict):abort(400,description='O corpo JSON deve ser um objeto.')
    return body

def serialize(row):
    return {k:row[k] for k in OUTPUT}

def digest(value):return sha256(value.encode()).hexdigest()

def local_transport():
    """HTTP permitido somente para testes no próprio computador, nunca LAN."""
    try:
        remote=ip_address(request.remote_addr or '')
        host=urlsplit(request.url).hostname
        return remote.is_loopback and (host=='localhost' or ip_address(host).is_loopback)
    except ValueError:return False

def register(app,get_db):
    app.config.setdefault('API_TOKEN_TTL',3600)
    app.config.setdefault('API_LOGIN_LIMIT',10)
    app.config.setdefault('API_LOGIN_WINDOW',300)
    if not 60<=app.config['API_TOKEN_TTL']<=86400:raise ValueError('API_TOKEN_TTL deve estar entre 60 e 86400 segundos.')
    # Mesma verificação de senha inclusive para conta inexistente.
    dummy_hash=generate_password_hash(secrets.token_urlsafe(32))
    bp=Blueprint('api_v1',__name__,url_prefix='/api/v1')

    @bp.before_request
    def require_transport():
        if not request.is_secure and not local_transport():return api_error_response(426)

    def authenticated(view):
        @wraps(view)
        def wrapped(*args,**kwargs):
            header=request.headers.get('Authorization','')
            match=re.fullmatch(r'Bearer ([A-Za-z0-9_-]{43})',header,re.IGNORECASE)
            if not match:abort(401)
            row=get_db().execute('''SELECT t.id token_id,t.credencial_hash,u.* FROM api_tokens t
                JOIN usuarios u ON u.id=t.usuario_id WHERE t.token_hash=? AND t.revogado_em IS NULL
                AND t.expira_em>? AND u.ativo=1 AND u.email!='operacao-local@sgdi.invalid' ''',
                (digest(match[1]),int(time.time()))).fetchone()
            if row is None or not secrets.compare_digest(row['credencial_hash'],digest(row['senha_hash'])):abort(401)
            g.usuario=row;g.api_authenticated=True;g.api_token_id=row['token_id']
            return view(*args,**kwargs)
        return wrapped

    def roles(*allowed):
        def decorator(view):
            @wraps(view)
            @authenticated
            def wrapped(*args,**kwargs):
                if g.usuario['perfil'] not in allowed:abort(403)
                return view(*args,**kwargs)
            return wrapped
        return decorator

    def find(demand_id):
        if not 1<=demand_id<=10**18:abort(404)
        row=get_db().execute('SELECT * FROM demandas WHERE id=?',(demand_id,)).fetchone()
        if row is None:abort(404)
        return row

    def history(demand_id,action):
        get_db().execute('INSERT INTO historico(demanda_id,usuario_id,acao,data) VALUES(?,?,?,?)',
            (demand_id,g.usuario['id'],action,datetime.now().isoformat(' ','seconds')))

    def validate(body,before=None):
        errors={key:'Campo não permitido.' for key in body if key not in FIELDS}
        data={k:before[k] for k in FIELDS} if before is not None else {'status':'aberta','prioridade':'media','responsavel_id':None,'prazo':None}
        data.update({k:v for k,v in body.items() if k in FIELDS})
        for key,minimum,maximum in [('titulo',3,200),('descricao',3,5000)]:
            value=data.get(key)
            if not isinstance(value,str) or not minimum<=len(value.strip())<=maximum:
                errors[key]=f'Informe texto com {minimum} a {maximum} caracteres.'
            else:data[key]=value.strip()
        for key,options in [('status',STATUS),('prioridade',PRIORIDADES)]:
            if not isinstance(data.get(key),str) or data[key] not in options:errors[key]='Valor inválido.'
        for key in ('solicitante_id','responsavel_id'):
            value=data.get(key)
            if key=='responsavel_id' and value is None:continue
            if type(value) is not int or not 1<=value<=10**18:
                errors[key]='Informe o ID inteiro de um usuário cadastrado.';continue
            # Relação inativa já existente é preservada; não pode ser recém-atribuída.
            if before is not None and before[key]==value:continue
            user=get_db().execute("SELECT perfil FROM usuarios WHERE id=? AND ativo=1 AND email!='operacao-local@sgdi.invalid'",(value,)).fetchone()
            if user is None:errors[key]='Usuário inexistente ou inativo.'
            elif key=='responsavel_id' and user['perfil']=='leitor':errors[key]='Leitor não pode ser responsável.'
        deadline=data.get('prazo')
        if deadline is not None:
            try:
                if not isinstance(deadline,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',deadline):raise ValueError
                date.fromisoformat(deadline)
            except ValueError:errors['prazo']='Use data válida no formato AAAA-MM-DD ou null.'
        if not body:errors['corpo']='Informe ao menos um campo.'
        if errors:raise ValidationError(errors)
        return data

    @bp.post('/auth/token')
    def issue_token():
        body=payload()
        if set(body)!={'email','senha'} or not isinstance(body.get('email'),str) or not isinstance(body.get('senha'),str):
            raise ValidationError({'credenciais':'Informe apenas email e senha em texto.'})
        if len(body['email'])>254 or len(body['senha'])>1024:raise ValidationError({'credenciais':'Credenciais fora dos limites.'})
        db=get_db();now=int(time.time());key=digest(request.remote_addr or 'desconhecido')
        # Contador persistente compartilhado entre processos. Reserva a tentativa antes de verificar.
        db.execute('DELETE FROM api_login_limites WHERE reinicia_em<=?',(now,))
        db.execute('''INSERT INTO api_login_limites(chave,tentativas,reinicia_em) VALUES(?,1,?)
            ON CONFLICT(chave) DO UPDATE SET tentativas=tentativas+1''',(key,now+app.config['API_LOGIN_WINDOW']))
        attempts=db.execute('SELECT tentativas,reinicia_em FROM api_login_limites WHERE chave=?',(key,)).fetchone()
        db.commit()
        if attempts['tentativas']>app.config['API_LOGIN_LIMIT']:
            response=api_error_response(429);response.headers['Retry-After']=str(max(1,attempts['reinicia_em']-now));return response
        user=db.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1 AND email!='operacao-local@sgdi.invalid'",(body['email'].strip().lower(),)).fetchone()
        valid=check_password_hash(user['senha_hash'] if user else dummy_hash,body['senha'])
        if not user or not valid:
            record(db,'autenticacao.falha',resource='api',result='falha');db.commit();abort(401)
        g.usuario=user;g.api_authenticated=True
        token=secrets.token_urlsafe(32);ttl=app.config['API_TOKEN_TTL']
        # Mantém no máximo 10 tokens ativos por conta; emissão e auditoria são atômicas.
        db.execute('DELETE FROM api_tokens WHERE usuario_id=? AND (expira_em<=? OR revogado_em IS NOT NULL)',(user['id'],now))
        old=db.execute('SELECT id FROM api_tokens WHERE usuario_id=? ORDER BY id DESC LIMIT -1 OFFSET 9',(user['id'],)).fetchall()
        db.executemany('UPDATE api_tokens SET revogado_em=? WHERE id=?',[(now,r['id']) for r in old])
        db.execute('INSERT INTO api_tokens(usuario_id,token_hash,credencial_hash,criado_em,expira_em) VALUES(?,?,?,?,?)',
            (user['id'],digest(token),digest(user['senha_hash']),now,now+ttl))
        record(db,'api.token_criado',resource='api');db.commit()
        return jsonify(data={'access_token':token,'token_type':'Bearer','expires_in':ttl,'usuario':{'id':user['id'],'perfil':user['perfil']}},request_id=g.request_id)

    @bp.delete('/auth/token')
    @authenticated
    def revoke_token():
        db=get_db();db.execute('UPDATE api_tokens SET revogado_em=? WHERE id=?',(int(time.time()),g.api_token_id))
        record(db,'api.token_revogado',resource='api');db.commit();return '',204

    @bp.get('/usuarios')
    @authenticated
    def users():
        allowed={'pagina','por_pagina','tipo'}
        if set(request.args)-allowed:abort(400,description='Parâmetro não permitido.')
        page,per_page=pagination()
        kind=request.args.get('tipo','solicitantes')
        if kind not in ('solicitantes','responsaveis'):abort(400,description='Tipo de usuário inválido.')
        db=get_db();where=" WHERE ativo=1 AND email!='operacao-local@sgdi.invalid'"
        if kind=='responsaveis':where+=" AND perfil!='leitor'"
        total=db.execute('SELECT COUNT(*) FROM usuarios'+where).fetchone()[0]
        pages=max(1,(total+per_page-1)//per_page);page=min(page,pages)
        rows=db.execute('SELECT id,nome FROM usuarios'+where+' ORDER BY nome,id LIMIT ? OFFSET ?',(per_page,(page-1)*per_page)).fetchall()
        record(db,'api.consultada','usuarios',count=len(rows));db.commit()
        return jsonify(data=[dict(row) for row in rows],meta={'total':total,'pagina':page,'paginas':pages,'por_pagina':per_page},request_id=g.request_id)

    def pagination():
        try:
            page=int(request.args.get('pagina','1'));per_page=int(request.args.get('por_pagina','10'))
            if not 1<=page<=10**9 or per_page not in (10,25,50):raise ValueError
        except ValueError:abort(400,description='Use pagina positiva e por_pagina igual a 10, 25 ou 50.')
        return page,per_page

    @bp.get('/demandas')
    @authenticated
    def list_demands():
        allowed={'q','status','prioridade','responsavel','solicitante','vencimento','ordenar','pagina','por_pagina'}
        if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400,description='Parâmetro inválido ou repetido.')
        page,per_page=pagination()
        today=app.config.get('REPORT_TODAY') or datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        selected=selecionar(request.args,today,strict=True);db=get_db()
        total,rows,page,pages=consultar(db,selected,page,per_page)
        record(db,'api.consultada','demandas',count=len(rows));db.commit()
        return jsonify(data=[serialize(row) for row in rows],meta={'total':total,'pagina':page,'paginas':pages,'por_pagina':per_page,'filtros':selected['filtros']},request_id=g.request_id)

    @bp.get('/demandas/<int:demanda_id>')
    @authenticated
    def get_demand(demanda_id):
        row=find(demanda_id);db=get_db();record(db,'api.consultada','demanda',demanda_id);db.commit()
        return jsonify(data=serialize(row),request_id=g.request_id)

    @bp.post('/demandas')
    @roles('administrador','gestor','colaborador')
    def create_demand():
        data=validate(payload());db=get_db();now=datetime.now().isoformat(' ','seconds')
        requester=db.execute('SELECT nome FROM usuarios WHERE id=?',(data['solicitante_id'],)).fetchone()[0]
        cursor=db.execute('''INSERT INTO demandas(titulo,descricao,solicitante_id,status,prioridade,responsavel_id,prazo,
            solicitante,criado_por_id,data_criacao,data_atualizacao,data_conclusao) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
            (*(data[k] for k in FIELDS),requester,g.usuario['id'],now,now,now if data['status']=='concluida' else None))
        demand_id=cursor.lastrowid;history(demand_id,'Demanda criada pela API')
        record(db,'demanda.criada','demanda',demand_id,changeset=changes({},data));row=find(demand_id);db.commit()
        response=make_response(jsonify(data=serialize(row),request_id=g.request_id),201)
        response.headers['Location']=url_for('api_v1.get_demand',demanda_id=demand_id)
        return response

    @bp.patch('/demandas/<int:demanda_id>')
    @roles('administrador','gestor')
    def update_demand(demanda_id):
        db=get_db()
        # Reserva a escrita antes da leitura para não sobrescrever atualizações concorrentes.
        db.execute('BEGIN IMMEDIATE')
        before=find(demanda_id);data=validate(payload(),before);now=datetime.now().isoformat(' ','seconds')
        requester=db.execute('SELECT nome FROM usuarios WHERE id=?',(data['solicitante_id'],)).fetchone()
        legacy_name=requester['nome'] if requester else before['solicitante']
        finished=(now if data['status']=='concluida' else None) if data['status']!=before['status'] else before['data_conclusao']
        db.execute('''UPDATE demandas SET titulo=?,descricao=?,solicitante_id=?,status=?,prioridade=?,responsavel_id=?,prazo=?,
            solicitante=?,data_atualizacao=?,data_conclusao=? WHERE id=?''',(*(data[k] for k in FIELDS),legacy_name,now,finished,demanda_id))
        history(demanda_id,'Demanda atualizada pela API');record(db,'demanda.alterada','demanda',demanda_id,changeset=changes(dict(before),data))
        row=find(demanda_id);db.commit();return jsonify(data=serialize(row),request_id=g.request_id)

    @bp.delete('/demandas/<int:demanda_id>')
    @roles('administrador')
    def delete_demand(demanda_id):
        db=get_db();db.execute('BEGIN IMMEDIATE');find(demanda_id)
        record(db,'demanda.excluida','demanda',demanda_id);db.execute('DELETE FROM demandas WHERE id=?',(demanda_id,));db.commit()
        return '',204

    @bp.get('/openapi.json')
    def openapi():return jsonify(json.loads(Path(app.root_path,'docs','openapi.json').read_text(encoding='utf-8')))

    @bp.errorhandler(ValidationError)
    def validation_error(error):
        get_db().rollback();return api_error_response(422,fields=error.fields)

    @bp.errorhandler(HTTPException)
    def http_error(error):
        get_db().rollback()
        # Só mensagens deliberadas de 400; erros internos nunca expõem detalhes.
        message=error.description if error.code==400 else None
        return api_error_response(error.code,message)

    @bp.errorhandler(sqlite3.Error)
    def storage_error(_error):
        get_db().rollback();g.audit_recorded=False
        app.logger.error('sgdi.api_storage_failure request_id=%s',g.request_id)
        return api_error_response(503)

    app.register_blueprint(bp)
    @app.get('/api/docs')
    def api_docs():
        return render_template('api_docs.html',api_spec=json.loads(Path(app.root_path,'docs','openapi.json').read_text(encoding='utf-8')))
