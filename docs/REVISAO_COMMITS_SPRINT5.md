# Revisão dos commits e integração até a Sprint 5

Revisão solicitada por Murilo em 27/10/2026. Base observada: `95dd27b` da
`main` de DALMOL1N/404. A análise cobre os commits publicados e as branches
disponíveis no momento da revisão; não comprova trabalho ainda não enviado.

## O que foi encontrado

| Integrante / registro | Evidência no Git | Resultado da revisão |
| --- | --- | --- |
| Ricardo / iWERNERi | `c02a975`: requisitos e checklist da Sprint 3 | Documentação publicada. Não foi localizado commit próprio com `init_db.py` atualizado ou `audit_schema.py` das Sprints 4/5. |
| Naubert | `6c48195`: adiciona `analytics.py` e `auditoria.py`; `ddb1584`, na branch `naubert-1-registro` | Os módulos correspondem aos componentes preparados para as Sprints 4/5. O segundo commit só remove a descrição inicial de `analytics.py`; não acrescenta funcionalidade. O primeiro usa a identidade Git genérica “Usuario 404”, sem associação pessoal verificável pelo autor configurado. |
| Gabriel | `cf668b7`: interface e templates; branch antiga `feature/atualizacao-interface` | A interface publicada corresponde à base da Sprint 3. Não foram localizados os componentes novos do dashboard e da auditoria das Sprints 4/5 nos commits disponíveis. |
| Tino | `c4561fc`: testes e evidências da Sprint 3 | Os testes foram publicados, mas o commit também inclui banco de execução e arquivos `__pycache__`. Não foram localizados os testes novos das Sprints 4/5. |
| Murilo | `3f0496b` e `17572af`, PR #3 | Integrações do dashboard e da auditoria publicadas. Corretas como parte da entrega, mas dependentes dos módulos, migração, interface e testes restantes. |

O commit `030f7be` de Naubert só adiciona `RELATORIO_MIGRACAO.md`; o nome do
commit não significa que a migração executável foi atualizada.

## Problemas de integração

- A `main` ainda tinha `init_db.py` legado, sem `initialize_database`, função
  já importada pela aplicação. Essa combinação impede inicialização normal.
- Adicionar `analytics.py` e `auditoria.py` sem o esquema, os pontos de registro,
  os templates e os testes não conclui as Sprints 4/5.
- Os arquivos de banco e bytecode não devem acompanhar a distribuição do código.
- A identidade Git genérica deve ser corrigida na configuração dos próximos
  commits. Esta integração não altera retroativamente autores ou commits.

## Integração realizada

As branches de Naubert e de Murilo foram incorporadas com merges que preservam
seus commits. Um commit de integração acrescenta os componentes ausentes da v5
já preparada e validada, sem atribuí-los retroativamente aos colegas:

- `init_db.py`, `audit_schema.py`: migração, backup e trilha independente.
- Dashboard, JavaScript, CSS, navegação e tela da auditoria.
- Testes das Sprints 4/5, evidências e relatório existente.
- Ajustes Windows da v5: `tzdata`, BATs, conexões SQLite temporárias fechadas,
  dependências por plataforma e workflow Windows/Linux.
- Banco e caches removidos do índice Git, mantendo o histórico e a cópia local.

O código resultante é comparado à v5 de DALMOL1N/406, commit `d392825`.
Arquivos exclusivos do histórico 404, como `docs` e evidências da Sprint 3,
são preservados. O novo filtro de prazo da Sprint 6 fica fora desta integração.

## Validação

Suíte local: 59 testes, incluindo as 56 regressões funcionais da v5 e os três
testes de portabilidade. Saída completa em
[`evidencias/testes-integracao-main-sprint5.txt`](../evidencias/testes-integracao-main-sprint5.txt).
O workflow executa a mesma suíte em Windows e Linux e verifica a inicialização
da demonstração e o preparador BAT. O resultado efetivo fica na aba Actions.

Cada integrante deve confirmar seu relato e seus commits reais. A integração
preparada com apoio de IA não substitui autoria individual nem aceite do cliente.
