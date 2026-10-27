
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
