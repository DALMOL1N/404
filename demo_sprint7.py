"""Demonstração local isolada, com 144 demandas e contas inteiramente fictícias."""
from pathlib import Path
import os
import secrets
from app import create_app
from dados_demonstracao import popular_demonstracao

PASSWORD='DemoSprint7!2026'  # Senha pública da demonstração; nunca usar com dados reais.
path=Path(os.environ.get('SGDI_DEMO_DATABASE',str(Path(__file__).with_name('demonstracao-sprint7.db'))))
app=create_app(dict(AUTH_REQUIRED=True,DEMONSTRACAO=True,DATABASE=str(path),SECRET_KEY=secrets.token_hex(32),
    ADMIN_INITIAL_PASSWORD=PASSWORD,COMPANY_NAME='Equipe 404 · Demonstração Sprint 7'))
resultado=popular_demonstracao(app,PASSWORD)
if __name__=='__main__':
    print('SGDI Sprint 7 | http://127.0.0.1:5070/')
    if app.config['API_V1_AVAILABLE']:print('Console da API: http://127.0.0.1:5070/api/docs')
    print(f"Demandas fictícias acrescentadas: {resultado['criadas']}; conjunto previsto: 144.")
    print('Conta fictícia: admin@404.local / '+PASSWORD)
    app.run(host='127.0.0.1',port=5070,debug=False)
