"""Esquema SQLite da auditoria independente do ciclo de vida das demandas."""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 instante TEXT NOT NULL,
 servico TEXT NOT NULL DEFAULT 'sgdi',
 evento TEXT NOT NULL,
 resultado TEXT NOT NULL CHECK(resultado IN ('sucesso','falha')),
 usuario_id INTEGER,
 identidade TEXT NOT NULL CHECK(identidade IN ('autenticada','local','anonima')),
 recurso TEXT NOT NULL,
 recurso_id INTEGER,
 request_id TEXT NOT NULL,
 detalhes_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auditoria_data ON auditoria(instante,id);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria(usuario_id,id);
CREATE INDEX IF NOT EXISTS idx_auditoria_evento ON auditoria(evento,id);
CREATE INDEX IF NOT EXISTS idx_auditoria_recurso ON auditoria(recurso,recurso_id,id);
CREATE TRIGGER IF NOT EXISTS auditoria_sem_edicao BEFORE UPDATE ON auditoria
 BEGIN SELECT RAISE(ABORT, 'Registros de auditoria não podem ser editados'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_sem_exclusao BEFORE DELETE ON auditoria
 BEGIN SELECT RAISE(ABORT, 'Registros de auditoria não podem ser excluídos'); END;
'''
