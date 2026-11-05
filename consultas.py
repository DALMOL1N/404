"""Consulta única para tela, CSV e API: filtros equivalentes, SQL parametrizado."""
import re
from datetime import timedelta
from flask import abort
from catalogo import STATUS, PRIORIDADES, SORTS, VENCIMENTOS

JOINS = ' FROM demandas d LEFT JOIN usuarios s ON s.id=d.solicitante_id LEFT JOIN usuarios u ON u.id=d.responsavel_id'

def selecionar(args,today,strict=False):
    f={k:args.get(k,'') for k in ('q','status','prioridade','responsavel','solicitante','vencimento')}
    if strict and len(f['q'].strip())>200:abort(400,description='Busca limitada a 200 caracteres.')
    f['q']=f['q'].strip()[:200]
    sort=args.get('ordenar','recentes')
    if strict and sort not in SORTS: abort(400,description='Ordenação inválida.')
    f['ordenar']=sort if sort in SORTS else 'recentes'
    for key,options in [('status',STATUS),('prioridade',PRIORIDADES),('vencimento',VENCIMENTOS)]:
        if f[key] and f[key] not in options:abort(400,description=f'Filtro de {key} inválido.')
    conditions=[];params=[]
    if f['q']:
        conditions.append("(d.titulo LIKE ? ESCAPE '\\' OR d.descricao LIKE ? ESCAPE '\\' OR COALESCE(s.nome,d.solicitante) LIKE ? ESCAPE '\\' OR CAST(d.id AS TEXT)=?)")
        escaped=f['q'].replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        params.extend([f'%{escaped}%']*3+[f['q']])
    for key in ('status','prioridade'):
        if f[key]:conditions.append('d.'+key+'=?');params.append(f[key])
    for key,column,special in [('responsavel','responsavel_id','sem'),('solicitante','solicitante_id','pendente')]:
        raw=f[key]
        if raw==special:conditions.append('d.'+column+' IS NULL')
        elif re.fullmatch(r'[0-9]{1,18}',raw):conditions.append('d.'+column+'=?');params.append(int(raw))
        elif raw:abort(400,description=f'Filtro de {key} inválido.')
    deadline=f['vencimento']
    if deadline=='sem_prazo':conditions.append("(d.prazo IS NULL OR d.prazo='')")
    elif deadline:
        conditions.append("d.status NOT IN ('concluida','cancelada')")
        if deadline=='atrasadas':conditions.append("d.prazo IS NOT NULL AND d.prazo<>'' AND d.prazo<?");params.append(today.isoformat())
        elif deadline=='hoje':conditions.append('d.prazo=?');params.append(today.isoformat())
        else:
            conditions.append('d.prazo BETWEEN ? AND ?')
            params.extend(((today+timedelta(days=1)).isoformat(),(today+timedelta(days=7)).isoformat()))
    return {'filtros':f,'where':' WHERE '+' AND '.join(conditions) if conditions else '', 'params':params}

def consultar(db,selected,page=1,per_page=None):
    where=selected['where'];params=list(selected['params'])
    total=db.execute('SELECT COUNT(*)'+JOINS+where,params).fetchone()[0]
    pages=max(1,(total+per_page-1)//per_page) if per_page else 1
    page=min(max(1,page),pages)
    sql='SELECT d.*,u.nome responsavel_nome,s.nome solicitante_nome'+JOINS+where+' ORDER BY '+SORTS[selected['filtros']['ordenar']]
    if per_page:sql+=' LIMIT ? OFFSET ?';params.extend((per_page,(page-1)*per_page))
    return total,db.execute(sql,params).fetchall(),page,pages
