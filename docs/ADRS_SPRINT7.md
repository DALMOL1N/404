# Decisões técnicas da Sprint 7

Registro técnico da versão preparada em 03/11/2026. A revisão do time e a confirmação das regras pelo cliente precisam ser registradas pela equipe.

## ADR 007 API versionada no próprio Flask

Contexto: o pedido da Sprint 7 exige consultar e manipular dados de outros sistemas, com autenticação e documentação. Decisão aplicada: blueprint /api/v1, JSON, operações GET/POST/PATCH/DELETE e contrato OpenAPI 3.0.3, usando o SQLite do SGDI. Benefícios: implantação simples, dados únicos, sem sincronização de duas bases, interface anterior preservada. Alternativa: serviço separado. Limitações: mesmo processo e banco da interface, contenção de escrita do SQLite e necessidade de revisar escala no futuro. Impacto: novos api.py, api_schema.py e documentação; migração aditiva com backup. A API interna antiga /api/dashboard continua servindo a interface e não integra o novo contrato externo.

## ADR 008 Token opaco com expiração e revogação

Decisão aplicada: credenciais de conta ativa em JSON geram Bearer aleatório de 256 bits com validade de uma hora. Só o SHA-256 é persistido. Conta técnica, cookies da interface e modo local nunca autenticam a API. O perfil é lido a cada chamada. Senha alterada ou conta inativa invalidam o token; revogação explícita disponível. Benefícios: sem nova dependência, segredo não guardado no banco e revogação imediata. Alternativa: JWT exigiria gestão de chave, prazo e lista de revogação; OAuth com provedor externo aumentaria configuração. Limitações: consulta ao banco por requisição, compartilhamento de perfis com contas humanas e necessidade de rotação pelo cliente. Não é servidor OAuth. HTTPS obrigatório fora do loopback; CORS não habilitado; limite persistente de emissões. Impacto: tabela api_tokens, nova API de autenticação e clientes que protejam o cabeçalho.

## ADR 009 Autorização e auditoria na mesma transação

Decisão aplicada: leitura por qualquer perfil ativo, criação por administrador/gestor/colaborador, alteração completa por administrador/gestor, exclusão por administrador. Segue permissões da edição completa da interface; regras específicas por unidade/solicitante ainda dependem do cliente. Toda escrita e evento usam uma transação. Token, senha, query string e textos livres não são copiados para auditoria. Benefícios: operação sem rastreio não é confirmada; redução de dados sensíveis no log. Alternativa: gravar log depois do commit reduziria indisponibilidade mas perderia atomicidade. Limitações: falha na auditoria bloqueia a operação (503), e os logs do SQLite não oferecem garantia contra administrador do arquivo. Identidade da API é autenticada inclusive no modo local. Impacto: novos eventos e ajustes em auditoria.py; exclusão da demanda preserva a auditoria independente.

## ADR 010 Uma consulta para tela CSV e API

Contexto: a contribuição externa da Sprint 6 duplicava os filtros entre tela e CSV; o filtro de prazo preparado na v6 não era conhecido dessa exportação. Decisão aplicada: consultas.py centraliza condições SQL parametrizadas, ordenação permitida, contagem e paginação. Benefícios: critérios de vencimento idênticos, correção testada em tela/CSV/API e menor manutenção. Alternativa: copiar o novo filtro três vezes manteria risco de divergência. Limitações: mudanças no módulo compartilhado afetam três saídas; CSV ainda exporta o conjunto inteiro e deve ter volume revisado antes de grandes bases. Impacto: refatoração localizada em app.py e testes de regressão, preservando a interface e as ações rápidas de Ricardo Drews.
