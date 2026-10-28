# Relatório de migração

Fonte preservada: `demandas-legado.db`.

Resultado incluído em `demandas.db`:

- 4 demandas válidas importadas;
- 1 demanda inválida descartada (título com menos de 3 caracteres);
- 2 comentários válidos importados;
- 0 comentários órfãos mantidos;
- 0 usuários predefinidos — o administrador é criado com `ADMIN_INITIAL_PASSWORD` na instalação;
- 0 violações no `PRAGMA foreign_key_check`.
- configuração e documentação técnica validada, .

O banco legado permanece intacto no ZIP. A rotina também foi testada com IDs duplicados, registros inválidos e comentário órfão; o teste automatizado confirma a deduplicação, o descarte e a criação do backup anterior à migração.
