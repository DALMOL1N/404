
from collections import Counter
from datetime import date, datetime, timedelta
from flask import abort

OPEN = {'aberta', 'em_analise', 'em_andamento', 'aguardando'}

def filters(args, statuses, priorities):
    result = {k: args.get(k, '').strip() for k in ('inicio', 'fim', 'responsavel', 'prioridade', 'status', 'criticas_atrasadas')}
    for k in ('inicio', 'fim'):
        if result[k]:
            try: date.fromisoformat(result[k])
            except ValueError: abort(400, description='Data inválida no filtro de período.')
    if result['inicio'] and result['fim'] and result['inicio'] > result['fim']:
        abort(400, description='O início deve ser anterior ou igual ao fim.')
    if result['status'] and result['status'] not in statuses: abort(400, description='Status inválido.')
    if result['prioridade'] and result['prioridade'] not in priorities: abort(400, description='Prioridade inválida.')
    if result['responsavel'] and result['responsavel'] != 'sem' and not (result['responsavel'].isascii() and result['responsavel'].isdigit() and int(result['responsavel']) > 0):
        abort(400, description='Responsável inválido.')
    if result['criticas_atrasadas'] not in ('', '0', '1'): abort(400, description='Visão inválida.')
    return result

def report(db, selected, statuses, priorities, today, critical_weight):
    conditions, params = [], []
    for key, sql in [('inicio', 'date(d.data_criacao)>=?'), ('fim', 'date(d.data_criacao)<=?')]:
        if selected[key]: conditions.append(sql); params.append(selected[key])
    for key in ('status', 'prioridade'):
        if selected[key]: conditions.append('d.'+key+'=?'); params.append(selected[key])
    if selected['responsavel'] == 'sem': conditions.append('d.responsavel_id IS NULL')
    elif selected['responsavel']: conditions.append('d.responsavel_id=?'); params.append(int(selected['responsavel']))
    if selected['criticas_atrasadas'] == '1':
        conditions.append("d.prioridade='critica' AND d.status NOT IN ('concluida','cancelada') AND date(d.prazo)<?")
        params.append(today.isoformat())
    sql = '''SELECT d.*, u.nome responsavel_nome, s.nome solicitante_nome FROM demandas d
             LEFT JOIN usuarios u ON u.id=d.responsavel_id LEFT JOIN usuarios s ON s.id=d.solicitante_id'''
    if conditions: sql += ' WHERE '+' AND '.join(conditions)
    sql += ' ORDER BY d.id'
    rows = [dict(r) for r in db.execute(sql, params).fetchall()]
    total = len(rows)
    def overdue(r): return bool(r['prazo'] and r['prazo'] < today.isoformat() and r['status'] in OPEN)
    durations = []
    valid_completion = set()
    invalid_dates = 0
    for r in rows:
        r['atrasada'] = overdue(r)
        r['status_nome'] = statuses[r['status']]
        r['prioridade_nome'] = priorities[r['prioridade']]
        if r['status'] == 'concluida':
            try:
                days = (datetime.fromisoformat(r['data_conclusao']) - datetime.fromisoformat(r['data_criacao'])).total_seconds()/86400
                if days < 0: raise ValueError()
                valid_completion.add(r["id"])
                durations.append((days, critical_weight if r['prioridade']=='critica' else 1))
            except (ValueError, TypeError): invalid_dates += 1
    count = Counter(r['status'] for r in rows)
    late = sum(r['atrasada'] for r in rows)
    eligible = [r for r in rows if r['responsavel_id'] is not None and r['prazo'] and r['status'] != 'cancelada']
    compliance = sum((r['data_conclusao'][:10] <= r['prazo']) if r['status']=='concluida' and r['data_conclusao'] else (not r['atrasada']) for r in eligible if r['status']!='concluida' or r['id'] in valid_completion)
    eligible = [r for r in eligible if r['status']!='concluida' or r['id'] in valid_completion]
    by_person = Counter((r['responsavel_id'], r['responsavel_nome'] or 'Sem responsável') for r in rows if r['status'] in OPEN)
    timeline = Counter(r['data_criacao'][:10] for r in rows)
    timeline_values = []
    if timeline:
        start=date.fromisoformat(min(timeline)); end=date.fromisoformat(max(timeline))
        if (end-start).days<=366:
            while start<=end:
                label=start.isoformat(); timeline_values.append({'nome':label,'total':timeline[label]}); start+=timedelta(days=1)
        else:
            monthly=Counter()
            for day,n in timeline.items(): monthly[day[:7]]+=n
            timeline_values=[{'nome':m,'total':n} for m,n in sorted(monthly.items())]
    return dict(filtros=selected, total=total, abertas=count['aberta'], em_aberto=sum(count[s] for s in OPEN), concluidas=count['concluida'], atrasadas=late,
        percentual_abertas=round(count['aberta']*100/total,1) if total else 0,
        percentual_concluidas=round(count['concluida']*100/total,1) if total else 0,
        percentual_atrasadas=round(late*100/total,1) if total else 0,
        media_dias=round(sum(d for d,w in durations)/len(durations),2) if durations else None,
        media_ponderada_dias=round(sum(d*w for d,w in durations)/sum(w for d,w in durations),2) if durations else None,
        peso_critica=critical_weight, concluidas_com_data=len(durations), concluidas_sem_data=invalid_dates,
        sla_elegiveis=len(eligible), sla_percentual=round(compliance*100/len(eligible),1) if eligible else None,
        sem_responsavel=sum(r['responsavel_id'] is None for r in rows),
        por_status=[{'nome':label,'total':count[key]} for key,label in statuses.items()],
        por_prioridade=[{'nome':label,'total':sum(r['prioridade']==key for r in rows)} for key,label in priorities.items()],
        por_responsavel=[{'id':key[0],'nome':key[1],'total':n} for key,n in sorted(by_person.items(),key=lambda x:(-x[1],x[0][1],x[0][0] or 0))],
        evolucao=timeline_values, criticas=[r for r in rows if r['prioridade']=='critica'],
        criticas_atrasadas=[r for r in rows if r['prioridade']=='critica' and r['atrasada']], demandas=rows)
