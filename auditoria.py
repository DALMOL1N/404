"""Auditoria central: metadados permitidos, sem cópia de textos pessoais."""
import json
import re
from datetime import date, datetime, timezone
from flask import Blueprint, Response, abort, current_app, g, render_template, request, url_for


EVENTOS = {
 'demanda.criada':'Demanda criada', 'demanda.alterada':'Demanda alterada',
 'demanda.excluida':'Demanda excluída', 'comentario.criado':'Comentário adicionado',
 'usuario.criado':'Usuário criado', 'usuario.situacao_alterada':'Situação do usuário alterada',
 'autenticacao.sucesso':'Login realizado', 'autenticacao.falha':'Login recusado',
 'sessao.encerrada':'Saída do sistema', 'acesso.negado':'Acesso negado',
 'requisicao.recusada':'Requisição recusada', 'operacao.recusada':'Operação recusada',
 'sistema.erro':'Erro interno', 'relatorio.exportado':'Relatório exportado',
 'auditoria.consultada':'Auditoria consultada', 'auditoria.exportada':'Auditoria exportada'
}
SAFE_FIELDS = {'status','prioridade','responsavel_id','solicitante_id','prazo','ativo','perfil'}
TEXT_FIELDS = {'titulo','descricao'}

def changes(before, after):
    """Textos livres: apenas a indicação de mudança. IDs não são nomes."""
    result = {}
    for field in SAFE_FIELDS | TEXT_FIELDS:
        if field in after and before.get(field) != after[field]:
            result[field] = {'alterado': True} if field in TEXT_FIELDS else {'antes':before.get(field), 'depois':after[field]}
    return result

def record(db, event, resource='sistema', resource_id=None, *, result='sucesso', changeset=None, actor=None, count=None):
    if event not in EVENTOS: raise ValueError('Evento de auditoria desconhecido')
    user = actor if actor is not None else g.get('usuario')
    mode = ('autenticada' if current_app.config['AUTH_REQUIRED'] else 'local') if user else 'anonima'
    details = {'rota':request.url_rule.rule if request.url_rule else 'desconhecida','metodo':request.method}
    if changeset:
        # Accept only internally generated field changes, never arbitrary form data.
        details['alteracoes'] = {k:v for k,v in changeset.items() if k in SAFE_FIELDS | TEXT_FIELDS}
    if count is not None: details['quantidade'] = int(count)
    db.execute('''INSERT INTO auditoria(instante,evento,resultado,usuario_id,identidade,recurso,recurso_id,request_id,detalhes_json)
                  VALUES(?,?,?,?,?,?,?,?,?)''', (
        datetime.now(timezone.utc).isoformat(timespec='milliseconds'), event,result,user['id'] if user else None,
        mode,resource,resource_id,g.request_id,json.dumps(details,ensure_ascii=False,separators=(',',':'))))
    g.audit_recorded = True

def selection(args):
    values={key:args.get(key,'').strip() for key in ('inicio','fim','usuario','evento','resultado','recurso_id','request_id')}
    conditions=[];params=[]
    for key in ('inicio','fim'):
        if values[key]:
            try:
                if len(values[key]) != 10: raise ValueError
                date.fromisoformat(values[key])
            except ValueError: abort(400,description='Data inválida no filtro de auditoria.')
    if values['inicio'] and values['fim'] and values['inicio']>values['fim']:abort(400,description='Período invertido.')
    if values['inicio']:conditions.append('instante>=?');params.append(values['inicio'])
    if values['fim']:conditions.append('instante<?');params.append(values['fim']+'T99')
    for key,column in [('usuario','usuario_id'),('recurso_id','recurso_id')]:
        if values[key]:
            if not re.fullmatch(r'[1-9][0-9]{0,17}',values[key]):abort(400,description='Identificador inválido.')
            conditions.append(column+'=?');params.append(int(values[key]))
    if values['evento']:
        if values['evento'] not in EVENTOS:abort(400,description='Evento inválido.')
        conditions.append('evento=?');params.append(values['evento'])
    if values['resultado']:
        if values['resultado'] not in ('sucesso','falha'):abort(400,description='Resultado inválido.')
        conditions.append('resultado=?');params.append(values['resultado'])
    if values['request_id']:
        if not re.fullmatch(r'[a-f0-9]{32}',values['request_id']):abort(400,description='Identificador de requisição inválido.')
        conditions.append('request_id=?');params.append(values['request_id'])
    return values, (' WHERE '+' AND '.join(conditions) if conditions else ''), params

def register(app,get_db,role_required):
    bp=Blueprint('auditoria',__name__)
    @bp.get('/auditoria')
    @role_required('administrador','gestor')
    def index():
        values,where,params=selection(request.args)
        try:page=int(request.args.get('pagina','1'))
        except ValueError:abort(400,description='Página inválida.')
        db=get_db();total=db.execute('SELECT COUNT(*) FROM auditoria'+where,params).fetchone()[0]
        pages=max(1,(total+24)//25);page=min(max(1,page),pages)
        rows=db.execute('SELECT * FROM auditoria'+where+' ORDER BY id DESC LIMIT 25 OFFSET ?',(*params,(page-1)*25)).fetchall()
        record(db,'auditoria.consultada',resource='auditoria',count=len(rows));db.commit()
        return render_template('auditoria.html',registros=rows,eventos=EVENTOS,filtros=values,total=total,pagina=page,paginas=pages,
            page_url=lambda n:url_for('auditoria.index',**values,pagina=n),export_url=url_for('auditoria.exportar',**values))
    @bp.get('/auditoria/exportar.json')
    @role_required('administrador','gestor')
    def exportar():
        values,where,params=selection(request.args);db=get_db()
        rows=db.execute('SELECT * FROM auditoria'+where+' ORDER BY id DESC LIMIT 1001',params).fetchall()
        if len(rows)>1000:abort(400,description='A exportação aceita até 1000 eventos. Restrinja os filtros.')
        output=[]
        for row in rows:
            entry=dict(row);entry['detalhes']=json.loads(entry.pop('detalhes_json'));output.append(entry)
        record(db,'auditoria.exportada',resource='auditoria',count=len(output));db.commit()
        body={'servico':'sgdi','gerado_em':datetime.now(timezone.utc).isoformat(),'fuso':'UTC','filtros':values,'quantidade':len(output),'eventos':output}
        return Response(json.dumps(body,ensure_ascii=False,indent=2),mimetype='application/json',headers={'Content-Disposition':'attachment; filename="sgdi-auditoria.json"'})
    app.register_blueprint(bp)
