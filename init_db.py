"""Criação e migração segura do banco SQLite do SGDI 2.0."""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "demandas.db"
VALID_STATUS = {"aberta", "em_analise", "em_andamento", "aguardando", "concluida", "cancelada"}
VALID_PRIORITIES = {"baixa", "media", "alta", "critica"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 nome TEXT NOT NULL CHECK (length(trim(nome)) BETWEEN 2 AND 120),
 email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 senha_hash TEXT NOT NULL,
 perfil TEXT NOT NULL DEFAULT 'colaborador' CHECK (perfil IN ('administrador','gestor','colaborador','leitor')),
 ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
 data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS demandas (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 titulo TEXT NOT NULL CHECK (length(trim(titulo)) BETWEEN 3 AND 200),
 descricao TEXT NOT NULL CHECK (length(trim(descricao)) BETWEEN 3 AND 5000),
 solicitante_id INTEGER REFERENCES usuarios(id) ON DELETE RESTRICT,
 solicitante TEXT NOT NULL CHECK (length(trim(solicitante)) BETWEEN 2 AND 200),
 status TEXT NOT NULL DEFAULT 'aberta' CHECK (status IN ('aberta','em_analise','em_andamento','aguardando','concluida','cancelada')),
 prioridade TEXT NOT NULL DEFAULT 'media' CHECK (prioridade IN ('baixa','media','alta','critica')),
 responsavel_id INTEGER,
 prazo TEXT,
 criado_por_id INTEGER,
 data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 data_atualizacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (responsavel_id) REFERENCES usuarios(id) ON DELETE SET NULL,
 FOREIGN KEY (criado_por_id) REFERENCES usuarios(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS comentarios (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 demanda_id INTEGER NOT NULL,
 comentario TEXT NOT NULL CHECK (length(trim(comentario)) BETWEEN 1 AND 5000),
 autor TEXT NOT NULL,
 usuario_id INTEGER,
 data TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE CASCADE,
 FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS historico (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 demanda_id INTEGER NOT NULL,
 usuario_id INTEGER,
 acao TEXT NOT NULL,
 detalhes TEXT,
 data TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE CASCADE,
 FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_demandas_status ON demandas(status);
CREATE INDEX IF NOT EXISTS idx_demandas_prioridade ON demandas(prioridade);
CREATE INDEX IF NOT EXISTS idx_demandas_responsavel ON demandas(responsavel_id);
CREATE INDEX IF NOT EXISTS idx_demandas_criacao ON demandas(data_criacao DESC);
CREATE INDEX IF NOT EXISTS idx_comentarios_demanda ON comentarios(demanda_id,data);
CREATE INDEX IF NOT EXISTS idx_historico_demanda ON historico(demanda_id,data DESC);
"""

def _table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def _columns(conn, table):
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}

def _normalized(value):
    text = " ".join(str(value or "").strip().split()).casefold()
    return unicodedata.normalize("NFKC", text)

def _valid_text(value, minimum, maximum):
    return minimum <= len(str(value or "").strip()) <= maximum

def _backup(path):
    target = path.with_name(f"{path.name}.legacy-backup-{datetime.now():%Y%m%d-%H%M%S}")
    with sqlite3.connect(path) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    return target

def _legacy_rows(conn, table):
    if not _table_exists(conn, table):
        return []
    return conn.execute(f'SELECT rowid AS _rowid_, * FROM "{table}" ORDER BY rowid').fetchall()

def _needs_rebuild(conn):
    if not _table_exists(conn, "demandas"):
        return False
    required = {"id","titulo","descricao","solicitante","status","prioridade","responsavel_id","criado_por_id","data_criacao","data_atualizacao"}
    pk_ok = any(row[1] == "id" and row[5] == 1 for row in conn.execute("PRAGMA table_info(demandas)"))
    return not pk_ok or not required.issubset(_columns(conn, "demandas"))

def _rebuild_legacy(conn):
    """Reconstrói o legado, mantendo apenas registros válidos, únicos e não órfãos."""
    demands, comments = _legacy_rows(conn, "demandas"), _legacy_rows(conn, "comentarios")
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in ("historico", "comentarios", "demandas"):
        if _table_exists(conn, table):
            conn.execute(f'ALTER TABLE "{table}" RENAME TO "_{table}_legado"')
    conn.executescript(SCHEMA)
    stats = {"demandas_importadas":0,"demandas_duplicadas":0,"demandas_invalidas":0,
             "comentarios_importados":0,"comentarios_duplicados":0,"comentarios_orfaos_ou_invalidos":0}
    seen, old_to_new, used_ids = {}, {}, set()
    for row in demands:
        keys = set(row.keys())
        title, description, requester = row["titulo"], row["descricao"], row["solicitante"]
        if not (_valid_text(title,3,200) and _valid_text(description,3,5000) and _valid_text(requester,2,200)):
            stats["demandas_invalidas"] += 1
            continue
        created = str(row["data_criacao"] or datetime.now().isoformat(" ", "seconds"))
        fingerprint = tuple(_normalized(v) for v in (title,description,requester,created))
        old_id = row["id"] if "id" in keys else None
        if fingerprint in seen:
            if old_id is not None: old_to_new.setdefault(old_id, seen[fingerprint])
            stats["demandas_duplicadas"] += 1
            continue
        safe_id = old_id if isinstance(old_id,int) and old_id > 0 and old_id not in used_ids else None
        status = row["status"] if "status" in keys and row["status"] in VALID_STATUS else "aberta"
        priority = row["prioridade"] if "prioridade" in keys and row["prioridade"] in VALID_PRIORITIES else "media"
        cursor = conn.execute("""INSERT INTO demandas
          (id,titulo,descricao,solicitante,status,prioridade,prazo,data_criacao,data_atualizacao)
          VALUES (?,?,?,?,?,?,?,?,?)""",
          (safe_id,str(title).strip(),str(description).strip(),str(requester).strip(),status,priority,
           row["prazo"] if "prazo" in keys else None,created,
           row["data_atualizacao"] if "data_atualizacao" in keys and row["data_atualizacao"] else created))
        new_id = safe_id or cursor.lastrowid
        used_ids.add(new_id); seen[fingerprint] = new_id
        if old_id is not None: old_to_new.setdefault(old_id,new_id)
        stats["demandas_importadas"] += 1
    seen_comments, used_comment_ids = set(), set()
    for row in comments:
        keys = set(row.keys())
        parent = old_to_new.get(row["demanda_id"] if "demanda_id" in keys else None)
        body = row["comentario"] if "comentario" in keys else None
        author = row["autor"] if "autor" in keys else None
        if not parent or not _valid_text(body,1,5000) or not _valid_text(author,1,200):
            stats["comentarios_orfaos_ou_invalidos"] += 1
            continue
        created = str(row["data"] or datetime.now().isoformat(" ","seconds")) if "data" in keys else datetime.now().isoformat(" ","seconds")
        fingerprint = (str(parent),_normalized(body),_normalized(author),_normalized(created))
        if fingerprint in seen_comments:
            stats["comentarios_duplicados"] += 1
            continue
        old_id = row["id"] if "id" in keys else None
        safe_id = old_id if isinstance(old_id,int) and old_id > 0 and old_id not in used_comment_ids else None
        cursor = conn.execute("INSERT INTO comentarios(id,demanda_id,comentario,autor,data) VALUES (?,?,?,?,?)",
                              (safe_id,parent,str(body).strip(),str(author).strip(),created))
        used_comment_ids.add(safe_id or cursor.lastrowid); seen_comments.add(fingerprint)
        stats["comentarios_importados"] += 1
    for table in ("_historico_legado","_comentarios_legado","_demandas_legado"):
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute("PRAGMA foreign_keys = ON")
    return stats

def _ensure_admin(conn, password):
    if conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone(): return False
    if not password or len(password) < 12:
        raise RuntimeError("Defina ADMIN_INITIAL_PASSWORD com pelo menos 12 caracteres para criar o administrador inicial.")
    conn.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES (?,?,?,'administrador')",
        (os.environ.get("ADMIN_INITIAL_NAME","Administrador"),
         os.environ.get("ADMIN_INITIAL_EMAIL","admin@404.local").strip().lower(),generate_password_hash(password)))
    return True

def initialize_database(database_path=DEFAULT_DATABASE, *, admin_password=None):
    path = Path(database_path); path.parent.mkdir(parents=True,exist_ok=True)
    existed = path.exists() and path.stat().st_size > 0
    needs_rebuild = False
    needs_requester_upgrade = False
    if existed:
        with sqlite3.connect(path) as probe:
            needs_rebuild = _needs_rebuild(probe)
            needs_requester_upgrade = _table_exists(probe, "demandas") and "solicitante_id" not in _columns(probe, "demandas")
    backup = _backup(path) if needs_rebuild or needs_requester_upgrade else None
    stats = {"backup": str(backup) if backup else None}
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON"); conn.execute("PRAGMA journal_mode = WAL")
            if needs_rebuild: stats.update(_rebuild_legacy(conn))
            conn.executescript(SCHEMA)
            # Preserve legacy names for explicit reconciliation; names are not identities.
            if "solicitante_id" not in _columns(conn, "demandas"):
                conn.execute("ALTER TABLE demandas ADD COLUMN solicitante_id INTEGER REFERENCES usuarios(id) ON DELETE RESTRICT")
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_demandas_solicitante ON demandas(solicitante_id);
                CREATE TRIGGER IF NOT EXISTS demanda_exige_solicitante_insert
                BEFORE INSERT ON demandas WHEN NEW.solicitante_id IS NULL
                BEGIN SELECT RAISE(ABORT, 'Solicitante cadastrado obrigatório'); END;
                CREATE TRIGGER IF NOT EXISTS demanda_preserva_solicitante_update
                BEFORE UPDATE OF solicitante_id ON demandas
                WHEN OLD.solicitante_id IS NOT NULL AND NEW.solicitante_id IS NULL
                BEGIN SELECT RAISE(ABORT, 'Vínculo do solicitante obrigatório'); END;
            """)
            stats["solicitantes_pendentes"] = conn.execute("SELECT COUNT(*) FROM demandas WHERE solicitante_id IS NULL").fetchone()[0]
            stats["admin_criado"] = _ensure_admin(conn,admin_password or os.environ.get("ADMIN_INITIAL_PASSWORD"))
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations: raise RuntimeError(f"Falha de integridade: {len(violations)} violação(ões) de chave estrangeira.")
    except Exception:
        if backup: shutil.copy2(backup,path)
        raise
    return stats

def main():
    parser = argparse.ArgumentParser(description="Inicializa ou migra o banco do SGDI 2.0.")
    parser.add_argument("--database",default=str(DEFAULT_DATABASE)); args = parser.parse_args()
    result = initialize_database(args.database)
    print("Banco pronto e validado.")
    for key,value in result.items():
        if value not in (None,False,0): print(f"- {key}: {value}")

if __name__ == "__main__": main()
