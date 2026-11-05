# Commits da Sprint 7 por integrante

A parte de integração de Murilo é publicada nesta etapa. O merge da Sprint 6 preserva o commit original de Ricardo Drews, do outro grupo, sem atribuir o código dele à equipe 404. Os quatro pacotes restantes precisam da revisão e do commit pessoal dos respectivos integrantes.

## Murilo Dalmolin

Integração dos filtros compartilhados, preparação da API, inicializadores e carga de 144 cenários fictícios. Arquivos: `app.py`, `consultas.py`, `catalogo.py`, `VERSION`, `dados_demonstracao.py`, `demo_sprint7.py`, `INICIAR_WINDOWS.bat`, `DEMO_SPRINT7_WINDOWS.bat`, `COMO_EXECUTAR_WINDOWS.txt`, `tests/test_integracao_sprint7.py` e estes dois guias de integração. A API só é ativada quando as demais partes estiverem presentes. Não é necessário refazer o commit de Murilo.

## Ricardo Werner

Mensagem sugerida: `feat(db): adicionar tokens e migracao da API`.

Arquivos: `api_schema.py` e `init_db.py`. Revisar hash/expiração/revogação dos tokens, limite de tentativas, migração, backup e integridade. Primeiro pacote dos colegas a integrar.

## Naubert

Mensagem sugerida: `feat(api): implementar autenticacao e operacoes REST`.

Arquivos: `api.py` e `auditoria.py`. Revisar Bearer obrigatório, perfis, CRUD, validação, erros JSON e auditoria transacional. Depende da estrutura do banco e dos módulos compartilhados já incluídos por Murilo.

## Gabriel

Mensagem sugerida: `feat(frontend): adicionar console e contrato da integracao`.

Arquivos: `templates/base.html`, `templates/index.html`, `templates/api_docs.html`, `static/api.css`, `static/api.js`, `docs/openapi.json`, `docs/API_SPRINT7.md`, `docs/ADRS_SPRINT7.md` e `docs/ROTEIRO_DISCORD_SPRINT7.txt`. Revisar contrato, console, filtros e celular. O pacote atualizado só mostra o link de integrações quando a API está disponível. Como PO, registrar as respostas e o aceite reais do cliente.

## Tino

Mensagem sugerida: `test: validar API e regressoes da sprint 7`.

Arquivos: `tests/test_sprint7.py`, `tests/test_prazos.py`, `.github/workflows/testes.yml`, `exemplos/cliente_api.py`, `README.md`, `docs/DIVISAO_COMMITS_SPRINT7.txt`, `docs/TRELLO_SPRINT7.txt`, `documentacao/RELATORIO_SPRINT_7.docx` e `evidencias/sprint7/`. Conferir os registros originais, repetir a suíte, atualizar o relatório com as revisões pessoais e resultados atuais e acompanhar a CI Windows/Linux. Este pacote deve entrar depois dos anteriores.

## Como preparar cada commit

Atualizar a cópia local sem apagar alterações próprias, criar uma branch a partir de `origin/main`, copiar somente os arquivos do pacote atualizado, revisar as diferenças e executar `python -m unittest discover -s tests -v`. Adicionar os caminhos específicos, fazer o commit pela própria conta, enviar a branch e abrir um PR para `main`.

A ordem proposta é Ricardo Werner, Naubert, Gabriel e Tino. A publicação da integração de Murilo não significa que os arquivos da API dos demais integrantes já estejam na main. Os arquivos foram preparados com assistência; a divisão não comprova autoria individual passada. Cada membro precisa revisar e registrar sua própria contribuição. Não criar commits no nome de colegas nem versionar banco, ambiente virtual ou segredos.

## Validação desta etapa

A base destinada à main passou em 68 testes locais, incluindo cinco regressões novas de integração: carga fictícia isolada, 144 registros, idempotência, preservação de edições, filtros/CSV e bloqueio de acesso externo sem Bearer. Registro: [testes da main](../evidencias/testes-main-integracao-sprint7.txt).

Uma cópia separada da main com os quatro pacotes dos colegas aplicados passou em 100 testes locais. Essa montagem comprova a compatibilidade técnica dos pacotes, sem afirmar publicação ou revisão pessoal por esses integrantes. Registro: [testes da montagem completa](../evidencias/testes-montagem-pacotes-sprint7.txt).
