# Integração da Sprint 7

A contribuição externa de Ricardo Drews na Sprint 6 foi incorporada preservando o commit original `25ac8b5110c6cb1f4c5cb0ceb79a30e9c4c0483f`, seu autor e o histórico anterior da equipe. A integração mantém os documentos e as evidências que já estavam na main.

A parte de Murilo acrescenta a consulta compartilhada entre listagem e CSV, o filtro de prazo no backend, os pontos de integração da API, a execução no Windows e uma demonstração local com 144 demandas fictícias. Os cenários cobrem todos os status e prioridades, quatro solicitantes, responsáveis diferentes, registros sem responsável e seis situações de prazo. A carga é exclusiva da demonstração autenticada, não substitui registros existentes e não duplica cenários ao reiniciar.

Execute `python demo_sprint7.py` ou `DEMO_SPRINT7_WINDOWS.bat`. Abra http://127.0.0.1:5070/. Conta fictícia `admin@404.local`, senha pública `DemoSprint7!2026`. O banco `demonstracao-sprint7.db` é separado do operacional e não é versionado.

## Partes que os colegas ainda devem revisar e publicar

- Ricardo Werner: `api_schema.py` e `init_db.py` com migração aditiva e backup.
- Naubert: `api.py` e `auditoria.py` com autenticação, permissões, JSON e auditoria da integração.
- Gabriel: templates, estilos, console, contrato OpenAPI e guias.
- Tino: testes da API e dos prazos, exemplo de cliente, CI, relatório e evidências.

A API REST v1 só é registrada quando os módulos de API/banco e os arquivos do contrato/console estiverem presentes. Erros de importação em módulos presentes não são ocultados. Enquanto os demais arquivos não estiverem publicados, a interface e as funções anteriores continuam funcionando, sem desativar CSRF e sem criar acesso externo anônimo. A versão completa preparada localmente possui a API; sua publicação no GitHub depende das partes acima.

Após cada pacote, reinicie o processo. Use branches individuais a partir da main atualizada e abra PRs. Não copie uma pasta inteira por cima dos commits anteriores, não crie commits com o nome de colegas e não envie banco, ambiente virtual ou segredos. Cada integrante deve revisar a parte, registrar sua contribuição e usar a própria conta.
