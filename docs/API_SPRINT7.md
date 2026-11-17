# API de integração do SGDI v7

Abra `/api/docs` para documentação e console local. Contrato OpenAPI 3.0.3: `/api/v1/openapi.json` ou `docs/openapi.json`. O console não grava tokens no navegador, não usa CDN e oculta o segredo da resposta de login.

## Demonstração

Windows: execute `DEMO_SPRINT7_WINDOWS.bat`. macOS/Linux: instale `requirements.txt` num ambiente virtual e execute `python demo_sprint7.py`. Endereço: http://127.0.0.1:5070/api/docs. Contas fictícias: `admin@404.local`, `gestor@example.test`, `colaborador@example.test` e `leitor@example.test`. Senha pública para todas: `DemoSprint7!2026`. Banco separado `demonstracao-sprint7.db`.

Para o sistema normal, `python app.py` mantém a interface local sem login. Para contas com senha própria, use `python iniciar_autenticado.py`, com banco separado `sgdi-autenticado.db` na porta 5056. Contas criadas no modo local têm senha aleatória; use o modo autenticado para configurar credenciais de integração. A API jamais aceita a conta técnica de operação local.

## Autenticação

`POST /api/v1/auth/token`, JSON `{"email":"...","senha":"..."}`. Retorna `data.access_token`, `token_type=Bearer`, `expires_in=3600` e ID/perfil do usuário. Esse endpoint é próprio do SGDI; não é uma implementação de OAuth. Envie o segredo somente no cabeçalho `Authorization: Bearer TOKEN`. Nunca em URL, arquivos versionados ou prints. SHA-256 do token opaco aleatório de 256 bits é persistido; o segredo só sai na emissão. Expira em uma hora. Até dez tokens ativos por conta; emissão adicional revoga o mais antigo. `DELETE /api/v1/auth/token` revoga o token usado (204). Desativação da conta ou troca da senha invalida o acesso; permissões consultam o perfil atual a cada requisição.

Limite persistente: dez tentativas de emissão a cada cinco minutos por IP direto, incluindo tentativas válidas. Excedente: 429 e `Retry-After`. IP é resumido com SHA-256 para a chave do contador; não se trata de anonimização garantida. Atrás de proxy todos podem compartilhar o mesmo limite, pois o SGDI não confia em X-Forwarded-For. Para uso público, ajustar política e limite no proxy confiável.

## Operações e perfis

| Operação | Leitor | Colaborador | Gestor | Administrador |
|---|---|---|---|---|
| GET /demandas e /demandas/ID | sim | sim | sim | sim |
| GET /usuarios | sim | sim | sim | sim |
| POST /demandas | não | sim | sim | sim |
| PATCH /demandas/ID | não | não | sim | sim |
| DELETE /demandas/ID | não | não | não | sim |

Prefixo de todas as operações: `/api/v1`. Esta matriz segue a edição completa já existente na interface. Não implementa segregação por solicitante ou unidade; leitores autenticados veem todas as demandas. Os textos de demandas só devem conter informações que possam ser compartilhadas com esses perfis. Validar com o cliente a matriz antes do uso com dados reais.

`GET /usuarios?tipo=solicitantes` retorna IDs e nomes de ativos. `tipo=responsaveis` exclui leitores. Paginação 10/25/50. Não expõe e-mails, senhas, perfis da lista nem conta técnica.

## Requisições e respostas

Envie JSON nas escritas. Cadastro obrigatório: `titulo` (3 a 200), `descricao` (3 a 5000), `solicitante_id` (inteiro de usuário ativo). Opcionais: `status` (padrão aberta), `prioridade` (media), `responsavel_id` (inteiro ou null), `prazo` (AAAA-MM-DD ou null). Status: aberta, em_analise, em_andamento, aguardando, concluida, cancelada. Prioridades: baixa, media, alta, critica. Responsável deve ser usuário ativo que não seja leitor. Relações inativas que já constem de uma demanda podem ser preservadas no PATCH. Campos desconhecidos são recusados. PATCH altera somente campos enviados. Criador e datas do sistema não são editáveis pelo cliente. Histórico legado é preservado no formato de data original; prazo e filtros de vencimento usam America/Sao_Paulo.

Criação concluída retorna 201 + Location. Consulta e PATCH retornam 200, `{"data":{...},"request_id":"..."}`. Listas incluem `meta` com total, pagina, paginas, por_pagina e filtros (em demandas). DELETE responde 204 sem corpo. IDs inexistentes: 404. Erros: `{"error":{"code":"...","message":"...","fields":{...}},"request_id":"..."}`; fields aparece na validação. Demais erros: 400, 401 + WWW-Authenticate, 403, 405, 413 (1 MB), 415, 422, 426 (HTTPS), 429 e 503. Todas as respostas têm Cache-Control no-store, X-Request-ID e X-Content-Type-Options nosniff. Uma página maior que o total é ajustada para a última página, como na interface.

`GET /demandas`: filtros q, status, prioridade, responsavel (ID ou sem), solicitante (ID ou pendente), ordenar (recentes, antigas, prioridade, prazo, titulo), vencimento (atrasadas, hoje, proximos_7_dias, sem_prazo), pagina e por_pagina (10/25/50). Vencem nos próximos sete dias significa de amanhã até hoje + 7, inclusive. Os filtros de atraso/hoje/próximos dias excluem concluídas e canceladas. Sem prazo inclui NULL/vazio legado e pode incluir encerradas. Tela, CSV e API compartilham a consulta SQL parametrizada.

## Exemplo externo

Execute `python exemplos/cliente_api.py` em outro terminal. O programa pede credenciais, autentica, consulta as demandas e revoga o token. Usa a biblioteca padrão do Python, sem acesso direto ao banco. Para cadastrar pelo console, use POST `/demandas` e o corpo de exemplo. Para alterar: PATCH `/demandas/ID`, `{"status":"concluida"}`. Exclusão por administrador: DELETE `/demandas/ID`.

## Auditoria e implantação

Ações de escrita e seu evento de auditoria usam a mesma transação; falha no registro impede salvar a operação. Consultas externas também são auditadas. O evento guarda ID/perfil de identidade autenticada, recurso, request_id, método e padrão da rota; não copia token, senha, e-mail, parâmetros da URL nem descrição. Título/descrição aparecem apenas como sinal de alteração. O endpoint público OpenAPI contém só o contrato. Não há endpoints externos para auditoria, usuários administrativos ou arquivos de banco.

HTTP é aceito apenas se destino e origem forem loopback. Fora do computador, HTTPS é exigido. Para implantação, habilite login na interface (`SGDI_REQUIRE_LOGIN=1`), defina SECRET_KEY e ADMIN_INITIAL_PASSWORD com pelo menos 12 caracteres; use servidor de aplicação e TLS. Não exponha o modo local nem o servidor de demonstração com contas públicas. Se TLS termina no proxy, configure `SGDI_TRUST_PROXY=1` somente atrás de exatamente um proxy confiável que sobrescreva X-Forwarded-Proto e impeça acesso direto ao processo. Sem essa configuração, conexão encaminhada por HTTP é recusada pela API. CORS não está habilitado: o cliente de integração é outro serviço, e o console é da mesma origem. Banco SQLite e limitador simples são adequados à demonstração; volume, distribuição, retenção de tokens e credenciais de serviço precisam de revisão antes de uma implantação maior.

## Referências técnicas

- Uso do cabeçalho Bearer e proteção de transporte: https://www.rfc-editor.org/rfc/rfc6750.html
- Segurança e CSRF no Flask: https://flask.palletsprojects.com/en/stable/web-security/
- Contrato OpenAPI 3.0.3: https://spec.openapis.org/oas/v3.0.3
