"""Inicializador local autenticado, com banco próprio e segredo persistente."""
import getpass
import os
import secrets
from pathlib import Path
from app import create_app

if __name__ == '__main__':
    base=Path(__file__).resolve().parent
    secret_path=base/'.session-secret'
    try:
        fd=os.open(secret_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        secret=secret_path.read_text().strip()
    else:
        secret=secrets.token_hex(32)
        with os.fdopen(fd,'w') as handle:handle.write(secret)
    database=base/'sgdi-autenticado.db'
    password=None
    if not database.exists():
        password=getpass.getpass('Senha inicial do administrador (mínimo 12 caracteres): ')
        if len(password)<12:raise SystemExit('A senha precisa ter pelo menos 12 caracteres.')
    application=create_app(dict(AUTH_REQUIRED=True,DATABASE=str(database),SECRET_KEY=secret,ADMIN_INITIAL_PASSWORD=password))
    print('Acesso: admin@404.local (ou ADMIN_INITIAL_EMAIL configurado).')
    application.run(host='127.0.0.1',port=5056,debug=False)
