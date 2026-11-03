# Relatório da Sprint 6 — Troca de Desenvolvedores (Onboarding, Clean Code e Manutenibilidade)

**Disciplina:** Engenharia de Software | Desenvolvimento Ágil  
**Repositório Recebido:** SGDI 404 v5 (Sistema de Gestão de Demandas Internas — Flask + SQLite)  
**Tópicos:** Clean Code, Documentação Técnica, Análise Crítica e Extensão de Funcionalidades

---

## 1. Recepção e Setup (Execução Estrita via `README.md`)

Seguindo estritamente as instruções do arquivo `README.md` e do guia complementar `COMO_EXECUTAR_WINDOWS.txt`:

1. **Ambiente e Dependências**:
   - O ambiente virtual `.venv` com Python 3.11+ foi configurado com os pacotes de `requirements.txt` (`Flask`, `tzdata` para suporte ao fuso `America/Sao_Paulo` no Windows e `gunicorn` condicional para Linux/macOS).
2. **Modos de Execução Testados**:
   - **Modo Local sem Login (`python app.py` — porta `5050`)**: Inicializa/migra automaticamente `demandas.db` e registra ações sob a conta técnica `Operação local`.
   - **Modo Demonstração Autenticada (`python demo_sprint5.py` — porta `5056`)**: Cria base isolada (`demonstracao-sprint5.db`) com contas fictícias (`admin@404.local`, `gestor@example.test`, `leitor@example.test`).
   - **Suíte de Testes (`python -m unittest discover -s tests -v`)**: Todos os **59 testes originais** executaram com sucesso em bancos temporários sem afetar o banco principal.

---

## 2. Mapeamento Estrutural da Codebase

| Arquivo / Diretório | Papel Arquitetural e Fluxo de Dados |
| :--- | :--- |
| `app.py` | Ponto de entrada principal e Application Factory (`create_app`). Concentra configuração, conexão SQLite por requisição (`g.db`), proteção CSRF, RBAC (`@login_required`, `@role_required`), validação de formulários e rotas HTTP. |
| `init_db.py` | Criação idempotente do esquema SQLite (`usuarios`, `demandas`, `comentarios`, `historico`), triggers de integridade de solicitante e migração não-destrutiva de bancos legados com geração de backup automático. |
| `database.py` | Context manager `sqlite_transaction()` que garante `commit`/`rollback` e fechamento explícito do descritor de arquivo SQLite (essencial para portabilidade no Windows). |
| `analytics.py` | Motor de indicadores do Dashboard Gerencial (`/` e `/api/dashboard`): calcula totais, percentuais, tempo médio simples e ponderado (peso 2 para críticas), SLA e evolução diária/mensal. |
| `auditoria.py` & `audit_schema.py` | Blueprint `/auditoria` e esquema da tabela `auditoria` protegida por triggers SQLite contra `UPDATE` e `DELETE`. Registra metadados e *changesets* sem vazar dados pessoais ou textos livres. |
| `templates/` & `static/` | 13 templates Jinja2 herdando de `base.html`, folha de estilos `style.css` e script `dashboard.js` para atualização assíncrona (`fetch`) dos gráficos em SVG/HTML. |
| `tests/` | Suíte de testes automatizados (`unittest`) dividida por entregas (`test_app.py`, `test_sprint2.py`, `test_sprint3.py`, `test_emergencial.py`, `test_sprint5.py`, `test_windows.py` e agora `test_sprint6.py`). |

### Local de Acoplamento das Novas Funcionalidades
As novas funcionalidades foram acopladas em `app.py` (após as rotas de operações de demandas), com pontos de entrada visuais em `templates/index.html` (cabeçalho da listagem de demandas) e `templates/detalhes.html` (barra lateral de detalhes da demanda), integrando-se nativamente às funções existentes de histórico (`audit()`) e auditoria central (`record()`).

---

## 3. Relatório de Fricção e Análise Crítica (25%)

### 3.1. Avaliação da Documentação (`README.md`)
* **Pontos Positivos**:
  - Excelente preocupação com portabilidade Windows/Linux/macOS (`INICIAR_WINDOWS.bat`, `PREPARAR_WINDOWS.bat` e documentação de `tzdata`).
  - Explicação transparente sobre decisões de negócio (regras de cálculo de SLA, pesos, política de privacidade da auditoria e contas de demonstração).
* **Lacunas e Fricções Encontradas**:
  1. **Estrutura Cumulativa ("Diário de Sprints") com Dados Conflitantes**: O `README.md` foi construído empilhando blocos de texto de cada Sprint (Sprint 3, Sprint Emergencial, Sprint 05, Compatibilidade). Como consequência, um novo desenvolvedor lê na linha 62 que existem *"31 testes"*, na linha 91 que existem *"40 testes"*, na linha 154 que existem *"56 testes"* e apenas na linha 162 descobre que o total real é *"59 testes"*.
  2. **Ausência de Mapa de Arquitetura e Rotas**: Não há uma seção explicando a divisão de responsabilidades entre `app.py`, `analytics.py`, `auditoria.py`, `init_db.py` e `database.py`, nem uma tabela de permissões por perfil (`administrador`, `gestor`, `colaborador`, `leitor`).
  3. **Falta de Instruções de Contribuição/Padrões**: Não documenta convenções de código, formatação ou como registrar novos eventos em `auditoria.py`.

### 3.2. Avaliação Crítica do Código Recebido (Clean Code & Legibilidade)
1. **Formatação Compactada ("Minificada") e Múltiplas Instruções por Linha**:
   - Em `app.py`, `analytics.py`, `auditoria.py`, `static/dashboard.js` e principalmente nos templates HTML (`templates/detalhes.html` possui **3.882 caracteres comprimidos em apenas 6 linhas**), o grupo original encadeou múltiplos comandos com ponto-e-vírgula (`;`) na mesma linha:
     - Exemplo em `app.py` (linha 120): `record(get_db(),'acesso.negado',result='falha');get_db().commit()`
     - Exemplo em `app.py` (linha 390): `name=value("nome","nome",2,120); email=value("email","e-mail",5,254); password=...`
   - **Impacto**: Aumenta drasticamente a carga cognitiva durante a leitura, dificulta o uso de *breakpoints* em depuradores e gera conflitos de *merge* em equipe.
2. **Funções Extensas e Violação do SRP (*Single Responsibility Principle*)**:
   - `create_app()` em `app.py` possui **413 linhas** e declara **25 funções internas aninhadas**, misturando configuração, camada de acesso a dados, autenticação, validação de formulários, geração de CSV e rotas HTTP.
   - `report()` em `analytics.py` (linhas 23–85) realiza 5 tarefas distintas na mesma função: montagem de query SQL dinâmica, verificação de atraso, cálculo de duração de resolução, cálculo de elegibilidade de SLA e agrupamento temporal (diário vs. mensal).
3. **Violações de DRY (*Don't Repeat Yourself*) e Strings Mágicas**:
   - O literal `'operacao-local@sgdi.invalid'` aparece **6 vezes** espalhado em queries SQL ao longo de `app.py` (linhas 67, 70, 146, 157, 162, 173, 404) sem uma constante centralizada.
   - A regra de preenchimento/limpeza de `data_conclusao` quando `status == "concluida"` é repetida manualmente nas rotas de criação e edição.
4. **Nomenclatura Pouco Reveladora de Intenção**:
   - Funções como `value(name, label, minimum, maximum)` (`app.py`, linha 135) não revelam que leem `request.form` e disparam efeitos colaterais (`flash()`).
   - `user_id(raw)` (`app.py`, linha 143) retorna três tipos semânticos diferentes (`None`, `False` ou `int`), exigindo verificações `is None or is False` no chamador.

---

## 4. Sugestões de Alterações (Exemplos Práticos de Clean Code)

> **Nota:** Conforme as diretrizes de não reescrever o código legado funcional da equipe original, as refatorações abaixo são apresentadas como **recomendações técnicas fundamentadas** para evolução da base, enquanto os princípios foram aplicados diretamente nas novas funcionalidades desenvolvidas na Seção 5.

### Sugestão 1 — Nomes com Intenção Revelada e Retorno Consistente (`app.py`)
```python
# COMO ESTÁ NO CÓDIGO LEGADO (nomes genéricos + múltiplos comandos por linha):
def value(name, label, minimum, maximum, required=True):
    result = request.form.get(name, "").strip()
    if required and not result:
        flash(f"O campo {label} é obrigatório.", "error"); return None
    if result and not minimum <= len(result) <= maximum:
        flash(f"{label.capitalize()} deve ter entre {minimum} e {maximum} caracteres.", "error"); return None
    return result

# SUGESTÃO CLEAN CODE (intenção clara + formatação legível):
def validar_campo_texto_formulario(nome_campo, rotulo_exibicao, tamanho_minimo, tamanho_maximo, obrigatorio=True):
    valor_limpo = request.form.get(nome_campo, "").strip()
    if obrigatorio and not valor_limpo:
        flash(f"O campo {rotulo_exibicao} é obrigatório.", "error")
        return None
    if valor_limpo and not (tamanho_minimo <= len(valor_limpo) <= tamanho_maximo):
        flash(f"{rotulo_exibicao.capitalize()} deve ter entre {tamanho_minimo} e {tamanho_maximo} caracteres.", "error")
        return None
    return valor_limpo
```

### Sugestão 2 — Eliminação de *Magic Strings* com Constantes (DRY)
```python
# COMO ESTÁ NO CÓDIGO LEGADO (repetido 6 vezes em app.py):
WHERE email != 'operacao-local@sgdi.invalid'

# SUGESTÃO CLEAN CODE (constante única no topo do módulo):
EMAIL_OPERACAO_LOCAL = "operacao-local@sgdi.invalid"
TAMANHO_MINIMO_SENHA = 12
FUSO_HORARIO_PADRAO = ZoneInfo("America/Sao_Paulo")
```

### Sugestão 3 — Decomposição de `report()` em Funções Pequenas com SRP (`analytics.py`)
Extrair de `report()` funções dedicadas com uma única responsabilidade:
- `verificar_demanda_atrasada(demanda, data_referencia_iso)`
- `calcular_duracoes_resolucao(demandas, peso_critica)`
- `calcular_indicadores_sla(demandas, ids_conclusao_valida)`
- `construir_serie_temporal_criacao(demandas)`

---

## 5. Novas Funcionalidades Implementadas (30% Funcionalidade + 25% Coerência de Estilo)

Para agregar valor real ao produto respeitando a arquitetura Flask + SQLite, os padrões visuais, a proteção CSRF, o controle de acesso (`@login_required` / `@role_required`) e a auditoria central (`record()`), implementamos **duas funcionalidades complementares**:

### Funcionalidade 1: Exportação CSV da Listagem de Demandas Filtradas (`GET /demandas/exportar.csv`)
* **Motivação**: Na seção *Limites conhecidos* do `README.md` (linha 78), a equipe original registrou que a exportação na tela de Demandas havia ficado pendente (existia exportação apenas para críticas atrasadas no Dashboard).
* **Implementação Clean Code (`app.py` + `templates/index.html`)**:
  - `sanitizar_celula_csv(valor)`: função pura com responsabilidade única para neutralizar *CSV Formula Injection* (`=`, `+`, `-`, `@`).
  - `consultar_demandas_filtradas(db, args)`: extrai e valida todos os filtros da listagem (`q`, `status`, `prioridade`, `responsavel`, `solicitante`, `ordenar`).
  - `exportar_demandas_csv()`: gera o arquivo `sgdi-demandas.csv` com BOM UTF-8 (`\ufeff`), delimitador `;`, metadados dos filtros aplicados e registra o evento `relatorio.exportado` (`resource="demandas"`) na tabela `auditoria`.
  - Botão **"Exportar CSV"** adicionado em `templates/index.html` preservando os filtros ativos na URL.

### Funcionalidade 2: Ações Rápidas na Demanda — Atualização Rápida de Status e "Assumir Demanda" (`POST /demandas/<id>/status` e `POST /demandas/<id>/assumir`)
* **Motivação (Correção de Lacuna Operacional)**:
  - No código original, usuários com perfil **`colaborador`** podiam ser atribuídos como responsáveis pelas demandas, mas a rota `/editar/<id>` exigia perfil `administrador` ou `gestor`. Assim, o colaborador responsável não conseguia atualizar o andamento (`em_andamento`, `concluida`) da própria demanda.
  - Além disso, alterar apenas o status exigia sair da tela de detalhes e reenviar todo o formulário de edição.
* **Implementação Clean Code (`app.py` + `templates/detalhes.html`)**:
  - `atualizar_status_rapido(demanda_id)`: permite que `administrador`, `gestor` e `colaborador` atualizem o status diretamente na barra lateral da demanda, preenchendo automaticamente `data_conclusao` ao concluir (ou limpando ao reabrir), gravando no `historico` da demanda e registrando o *changeset* `{"status": {"antes": ..., "depois": ...}}` na `auditoria` central.
  - `assumir_demanda(demanda_id)`: permite que o usuário autenticado assuma rapidamente a responsabilidade pela demanda com 1 clique, registrando histórico e auditoria (`changeset` de `responsavel_id`).

### Verificação e Testes Automatizados (`tests/test_sprint6.py`)
Foram adicionados **4 novos testes abrangentes** em `tests/test_sprint6.py`, elevando a suíte de **59 para 63 testes automatizados** (100% aprovados, zero regressões):
- `test_exportacao_csv_demandas_respeita_filtros_sanitiza_e_audita`
- `test_exportacao_csv_rejeita_filtros_invalidos_e_exige_login`
- `test_atualizacao_rapida_de_status_por_colaborador_e_registro_conclusao`
- `test_assumir_demanda_e_bloqueio_para_leitor`

---

## 6. Reflexão, Autocrítica e Lições Aprendidas para o Nosso Próprio Grupo (20%)

A experiência de assumir um repositório sem comunicação com os autores originais evidenciou práticas essenciais que levaremos imediatamente para o repositório do nosso próprio grupo:

1. **Legibilidade Visual Supera Economia de Linhas**:
   - Compactar código Python e templates Jinja2 em linhas únicas com `;` economiza espaço vertical, mas penaliza severamente quem chega ao projeto. No nosso repositório, adotaremos formatação padronizada (1 instrução por linha, indentação semântica nos templates HTML e uso de *linter/formatter* como `ruff` ou `black`).
2. **README Orientado ao Estado Atual (Não um Diário de Sprints)**:
   - Manter textos antigos de sprints passadas no topo do `README.md` confunde novos desenvolvedores. No nosso projeto, manteremos o `README.md` refletindo sempre o **estado atual consolidado** (com um diagrama/tabela da arquitetura de arquivos e matriz de permissões) e moveremos o histórico de entregas anteriores para um `CHANGELOG.md`.
3. **Modularização desde Cedo (Evitar o "God File")**:
   - Concentrar todas as rotas e helpers dentro de `create_app()` dificulta o reuso e a navegação. No nosso repositório, separaremos claramente `routes/`, `services/` (regras de negócio) e `validators/`, facilitando a acoplagem de novas features por qualquer membro do time.
4. **Testes Automatizados dão Segurança para Evoluir Código Alheio**:
   - A presença dos 59 testes da equipe original foi decisiva para implementarmos novas funcionalidades com total confiança de que não introduzimos regressões. Manteremos e ampliaremos essa disciplina de testes no nosso próprio projeto.
