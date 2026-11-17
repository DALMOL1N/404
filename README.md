<p align="center">
  <img src="static/logo-404.jpeg" alt="Logo da Equipe 404" width="180">
</p>

<h1 align="center">SGDI 404</h1>

<p align="center">Sistema de Gestão de Demandas Internas</p>

[![Testes Windows e Linux](https://github.com/DALMOL1N/404/actions/workflows/testes.yml/badge.svg)](https://github.com/DALMOL1N/404/actions/workflows/testes.yml)

Aplicação para organizar solicitações, acompanhar prazos e consultar o histórico das operações.

**Tecnologias:** Python 3.11+, Flask, SQLite, HTML, CSS e JavaScript.

## Funcionalidades

- Cadastro de demandas, usuários, comentários e histórico.
- Busca, filtros combinados por status, prioridade, responsável, solicitante e prazo.
- Paginação, exportação CSV e ações rápidas.
- Dashboard gerencial, permissões por perfil e auditoria.

**API REST da Sprint 7:** autenticação Bearer, operações de demandas e contrato OpenAPI. Com o sistema aberto, acesse o console em **http://127.0.0.1:5070/api/docs**. [Guia da API](docs/API_SPRINT7.md).

## Executar

### Windows

Instale **Python 3.11 ou superior**, extraia o ZIP do repositório e abra **`DEMO_SPRINT7_WINDOWS.bat`**. A primeira execução precisa de internet.

### macOS e Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python demo_sprint7.py
```

Acesse **http://127.0.0.1:5070/**.

| Acesso da demonstração | Valor |
| --- | --- |
| E-mail | `admin@404.local` |
| Senha | `DemoSprint7!2026` |

A demonstração única reúne **144 demandas fictícias** em banco separado, com criação distribuída por datas diferentes e conclusões após 1, 3, 5 ou 10 dias (críticas com acréscimo de 3 dias). Assim, filtros, evolução e tempos de resolução podem ser demonstrados juntos. Essas credenciais são públicas e exclusivas para testes. Para usar senha própria, execute `python iniciar_autenticado.py`. Encerre o servidor com **Ctrl+C**.

## Testes

Com o ambiente virtual ativado:

```bash
python -m unittest discover -s tests -v
```

Os testes utilizam bancos temporários. Resultados automáticos: [GitHub Actions](https://github.com/DALMOL1N/404/actions/workflows/testes.yml). Registros e imagens: [evidências](evidencias/).

## Equipe 404

| Integrante | Responsabilidade na G2 |
| --- | --- |
| Ricardo Werner | Banco de dados |
| Naubert Migliavacca | Backend e segurança |
| Murilo Dalmolin | Tech Lead e integração |
| Gabriel Granja | Product Owner e frontend |
| Tino Navarro | Testes e entrega |

Contribuição externa da Sprint 6: **Ricardo Drews**, com o commit original preservado.
