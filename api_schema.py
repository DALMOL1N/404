"""Migração aditiva da Sprint 7. Tokens brutos nunca são persistidos."""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS api_tokens (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE CHECK(length(token_hash)=64),
 credencial_hash TEXT NOT NULL CHECK(length(credencial_hash)=64),
 criado_em INTEGER NOT NULL,
 expira_em INTEGER NOT NULL,
 revogado_em INTEGER
);
CREATE INDEX IF NOT EXISTS idx_api_tokens_usuario ON api_tokens(usuario_id);
CREATE TABLE IF NOT EXISTS api_login_limites (
 chave TEXT PRIMARY KEY,
 tentativas INTEGER NOT NULL,
 reinicia_em INTEGER NOT NULL
);
'''
