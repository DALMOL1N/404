STATUS = {"aberta":"Aberta","em_analise":"Em análise","em_andamento":"Em andamento","aguardando":"Aguardando","concluida":"Concluída","cancelada":"Cancelada"}
PRIORIDADES = {"baixa":"Baixa","media":"Média","alta":"Alta","critica":"Crítica"}
PERFIS = {"administrador":"Administrador","gestor":"Gestor","colaborador":"Colaborador","leitor":"Leitor"}
SORTS = {
    "recentes": "d.data_criacao DESC, d.id DESC",
    "antigas": "d.data_criacao ASC, d.id ASC",
    "prioridade": "CASE d.prioridade WHEN 'critica' THEN 1 WHEN 'alta' THEN 2 WHEN 'media' THEN 3 ELSE 4 END, d.data_criacao DESC, d.id DESC",
    "prazo": "d.prazo IS NULL, d.prazo ASC, d.id DESC",
    "titulo": "d.titulo COLLATE NOCASE ASC, d.id ASC",
}
VENCIMENTOS = {"":"Todos os prazos","atrasadas":"Atrasadas","hoje":"Vencem hoje","proximos_7_dias":"Vencem nos próximos 7 dias","sem_prazo":"Sem prazo definido"}
