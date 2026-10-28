# SGDI 404 v5 — Windows, macOS e Linux

Aplicação Flask + SQLite para gestão de demandas, painel gerencial e auditoria. O menu permite escolher demonstração autenticada, uso local sem login ou acesso com senha própria.

## Windows — execução com dois cliques

Instale **Python 3.11 ou superior**, baixe o projeto por **Code → Download ZIP**,
extraia a pasta inteira e abra **INICIAR_WINDOWS.bat**. A instalação inicial precisa
de internet. O menu prepara `.venv` e oferece quatro opções:

1. **Demonstração Sprint 5:** http://127.0.0.1:5056, conta `admin@404.local`, senha
   pública fictícia `DemoSprint5!2026`.
2. **Sistema local sem login:** http://127.0.0.1:5050.
3. **Autenticado com senha própria:** http://127.0.0.1:5056, senha inicial escolhida
   no terminal. Banco e chave próprios, separados da demonstração.
4. **Testes:** executa toda a suíte em bancos temporários.

Pare com **Ctrl+C**. As opções 1 e 3 compartilham a porta 5056: use uma por vez.
Instruções manuais: [COMO_EXECUTAR_WINDOWS.txt](COMO_EXECUTAR_WINDOWS.txt).
O projeto inclui `tzdata` para o fuso de São Paulo, fecha conexões SQLite temporárias
explicitamente e instala Gunicorn somente fora do Windows.

[![Testes Windows e Linux](https://github.com/DALMOL1N/404/actions/workflows/testes.yml/badge.svg)](https://github.com/DALMOL1N/404/actions/workflows/testes.yml)

O workflow executa os testes em Windows e Linux com Python 3.12. Consulte a aba
Actions para verificar o resultado da versão publicada. Os logs antigos em
`evidencias` continuam identificando a validação original da Sprint 5 em macOS.



## Executar

Use Python 3.11 ou superior. Dentro desta pasta:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Abra http://127.0.0.1:5050. O banco demandas.db é criado ou migrado automaticamente; os dados existentes são preservados e as migrações que alteram o esquema criam backup. Demandas antigas cujo solicitante era texto livre ficam com vínculo pendente: selecione manualmente o usuário correto na edição.

No modo local, operações são registradas como **Operação local**. Essa conta não aparece na escolha de solicitante/responsável. O cadastro de pessoas não exige senha no modo local. Todos que acessarem essa instância local poderão operar com os mesmos privilégios. O servidor inicia apenas em 127.0.0.1; o modo local é destinado à demonstração/uso na própria máquina.

## Sprint 3

- Filtros por status, prioridade, responsável e solicitante combinados com busca.
- Consulta de demandas sem responsável e responsáveis inativos históricos.
- 10, 25 ou 50 registros por página; números, primeira/última e salto direto.
- Filtros e ordenação preservados ao navegar; novo filtro volta à primeira página.
- Ordenação com desempate por ID, limites de página tratados e estado vazio.
- Edição preserva responsável inativo existente; novo vínculo exige usuário ativo.
- Integra a Sprint 2: solicitante por ID, relatório, migração e histórico.

## Verificação

```sh
python3 -m unittest discover -s tests -v
```

31 testes, em bancos temporários. Os testes do modo autenticado continuam sendo executados para evitar regressão. Não executar esses testes contra o banco de produção; a suíte já cria seus próprios bancos.

## Demonstração isolada

```sh
python3 demonstracao.py
```

Abra http://127.0.0.1:5053. Esse comando usa `demonstracao.db`, separado de `demandas.db`, com 63 demandas fictícias e contas de exemplo. Não é necessário apagar dados do projeto para demonstrar a entrega.

## Autenticação opcional

Para uma instância que precise de login, configure `SGDI_REQUIRE_LOGIN=1` e `SECRET_KEY` (valor aleatório forte). Para um banco novo nesse modo, configure também `ADMIN_INITIAL_PASSWORD` com pelo menos 12 caracteres. Consulte init_db.py para a inicialização. A chave deve ser mantida entre reinícios em uma instalação compartilhada. O modo local gera uma chave temporária a cada execução.

## Limites conhecidos

A paginação usa LIMIT/OFFSET; alterações concorrentes podem deslocar páginas. A validação executada usa 63 registros, sem caracterizar teste de carga. Exportação e múltiplos valores no mesmo filtro estão fora desta entrega. Regras propostas e aceite do cliente devem ser confirmados pelo PO.


## Sprint Emergencial

O painel gerencial inclui contagens e percentuais, críticas e críticas atrasadas, volume em aberto por responsável, médias de resolução, gráficos e filtros combinados. A exportação CSV contém somente críticas atrasadas e respeita os demais filtros. Nome da empresa: variável SGDI_COMPANY_NAME (padrão Equipe 404).

A data de conclusão passa a ser registrada ao concluir uma demanda e é preservada em edições sem mudança de status. Reabertura remove essa data; uma nova conclusão mede o intervalo desde a criação original até a última conclusão. A migração cria backup antes de adicionar a coluna e não inventa datas para o legado.

Escolhas documentadas, a validar pelo PO: peso 2 para críticas na média ponderada; dias corridos; filtro pela data de criação; SLA medido pelo prazo cadastrado, com exclusão de canceladas, sem prazo, sem responsável e concluídas sem data válida. Demandas abertas ainda no prazo contam como regulares na data da consulta.

Execute python3 demo_emergencial.py e abra http://127.0.0.1:5054 para uma demonstração isolada com 48 registros fictícios. O sistema normal continua sendo executado com python3 app.py em 5050.

40 testes automatizados. Os cálculos carregam o conjunto filtrado em memória; esta entrega foi verificada com bases pequenas e não caracteriza teste de carga. O modo local sem login é destinado à demonstração na própria máquina.

## Sprint 05 — auditoria central

Versão preparada em 20/10/2026. A auditoria em `/auditoria` registra autenticação,
saída, demandas criadas/alteradas/excluídas, comentários (sem corpo), usuários,
recusas de acesso/validação, erros internos, consulta e exportação da auditoria e
exportação do painel. Admin e gestor podem consultar e exportar JSON; os demais
perfis recebem 403. Cada requisição recebe um UUID novo em X-Request-ID.

### Demonstração para aula

Instale as dependências (`python3 -m pip install -r requirements.txt`) e execute:

    python3 demo_sprint5.py

Abra http://127.0.0.1:5056. Use `admin@404.local`, `gestor@example.test` ou
`leitor@example.test`, com senha `DemoSprint5!2026`. São contas fictícias e a senha
é pública: use apenas a base de demonstração. As ações iniciais são feitas pelo
cliente HTTP de teste e geram registros reais sobre os dados fictícios. Não são
conversas, decisões ou atividades reais da equipe. O banco da demo é separado.

### Uso autenticado local com suas próprias contas

    python3 iniciar_autenticado.py

Na primeira execução, escolha a senha do administrador (mínimo 12 caracteres).
Banco próprio: `sgdi-autenticado.db`; chave de sessão persistente: `.session-secret`
(permissão restrita no macOS/Linux; não versionar). Porta 5056. Não execute ao mesmo
tempo que a demonstração na mesma porta. Para configurar um banco existente, use
`SGDI_REQUIRE_LOGIN=1`, `SECRET_KEY`, `DATABASE_PATH` e a credencial já cadastrada.
Contas antigas do modo sem login possuem senhas aleatórias e não servem como
credenciais pessoais. Faça uma migração de acesso planejada antes de uso real.

`python3 app.py` continua abrindo o modo local sem login, na porta 5050. Nesse modo,
a conta técnica tem acesso administrativo e TODOS os eventos são atribuídos à
operação local: esse modo não fornece autoria humana nem controle por pessoa.

### Política de auditoria implementada

- UTC, ID do usuário, tipo de identidade, evento/resultado, recurso/ID, request_id,
  rota padronizada e método. Não são registrados IP, cookies, senha, e-mail, nome,
  corpo de comentário ou valores livres de título/descrição.
- Alterações de status, prioridade, responsável/solicitante (IDs), prazo, perfil e
  situação guardam antes/depois; título/descrição guardam apenas `alterado: true`.
- Uma transação grava a mudança de negócio e o evento; falha do log reverte a mudança.
- A tabela não possui exclusão em cascata. Triggers barram UPDATE/DELETE comuns.
  Um administrador com acesso ao arquivo SQLite ainda pode remover os triggers:
  isto NÃO constitui armazenamento inviolável ou auditoria criptográfica.
- Histórico v4 permanece separado. Não inventamos registros anteriores à implantação.
- Migração cria backup SQLite antes de acrescentar a tabela ao banco v4.
- Consulta paginada em 25, filtros por data UTC, usuário, evento, resultado, recurso
  e requisição; exportação até 1000 eventos. Acima disso, exige restringir filtros.
- Sem expurgo automático até o cliente definir retenção e autorização. O banco
  crescerá; acompanhar volume, preservar backups com acesso restrito e planejar
  retenção. Não há política de prazo acordada, serviço externo de logs, alertas,
  rate limiting ou rastreamento distribuído nesta entrega.
- Falhas internas no console usam mensagem fixa e request_id; sem payload de exceção.

### Testes e evidências

    python3 -m unittest discover -s tests -v

56 testes (40 regressões + 16 cenários Sprint 05). Evidências em `evidencias/`:
`testes-sprint5.txt`, `verificacao-navegador.txt`, imagens e `auditoria-exportada.json`.
Prints usam a base fictícia da demonstração; não representam dados reais do cliente.
Windows: use `py` no lugar de `python3`. Não testado em Windows nesta entrega.

## Compatibilidade de 27/10/2026

Além dos 56 testes anteriores, três regressões verificam fechamento e rollback
SQLite e disponibilidade do fuso horário. Total: **59 testes**. Os testes no CI
usam `PYTHONTZPATH` vazio para exercitar o pacote `tzdata`.
As conexões da aplicação por requisição continuam fechadas no teardown do Flask.

Fontes técnicas: [zoneinfo e Windows](https://docs.python.org/3/library/zoneinfo.html#data-sources)
e [context manager do SQLite](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager).
