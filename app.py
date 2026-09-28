"""SGDI 2.0 — aplicação Flask segura para gestão de demandas."""
from __future__ import annotations

import hmac
import os
import re
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from init_db import initialize_database

BASE_DIR = Path(__file__).resolve().parent
STATUS = {"aberta":"Aberta","em_analise":"Em análise","em_andamento":"Em andamento","aguardando":"Aguardando","concluida":"Concluída","cancelada":"Cancelada"}
PRIORIDADES = {"baixa":"Baixa","media":"Média","alta":"Alta","critica":"Crítica"}
PERFIS = {"administrador":"Administrador","gestor":"Gestor","colaborador":"Colaborador","leitor":"Leitor"}
SORTS = {
    "recentes": "d.data_criacao DESC, d.id DESC",
    "antigas": "d.data_criacao ASC, d.id ASC",
    "prioridade": "CASE d.prioridade WHEN 'critica' THEN 1 WHEN 'alta' THEN 2 WHEN 'media' THEN 3 ELSE 4 END, d.data_criacao DESC, d.id DESC",
    "prazo": "d.prazo IS NULL, d.prazo ASC, d.id DESC",
    "titulo": "d.titulo COLLATE NOCASE ASC, d.id ASC",
}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE_PATH", str(BASE_DIR / "demandas.db")),
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production",
        MAX_CONTENT_LENGTH=1_000_000,
        PER_PAGE=10,
        AUTH_REQUIRED=os.environ.get("SGDI_REQUIRE_LOGIN") == "1",
    )
    if test_config: app.config.update(test_config)
    if not app.config["AUTH_REQUIRED"]:
        app.config["SECRET_KEY"] = app.config.get("SECRET_KEY") or secrets.token_hex(32)
        app.config["ADMIN_INITIAL_PASSWORD"] = app.config.get("ADMIN_INITIAL_PASSWORD") or secrets.token_urlsafe(32)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY não definida. Consulte o README para gerar uma chave segura.")
    initialize_database(app.config["DATABASE"], admin_password=app.config.get("ADMIN_INITIAL_PASSWORD"))

    if not app.config["AUTH_REQUIRED"]:
        with sqlite3.connect(app.config["DATABASE"]) as db:
            actor = db.execute("SELECT id FROM usuarios WHERE email='operacao-local@sgdi.invalid'").fetchone()
            if actor is None:
                cursor = db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES(?,?,?,'administrador')",
                    ('Operação local','operacao-local@sgdi.invalid',generate_password_hash(secrets.token_urlsafe(48))))
                app.config['LOCAL_ACTOR_ID'] = cursor.lastrowid
            else:
                app.config['LOCAL_ACTOR_ID'] = actor[0]
                db.execute("UPDATE usuarios SET ativo=1,perfil='administrador' WHERE id=?", (actor[0],))

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
            g.db.execute("PRAGMA busy_timeout = 10000")
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None: db.close()

    @app.before_request
    def prepare_request():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        g.usuario = None
        if not app.config['AUTH_REQUIRED']:
            g.usuario = get_db().execute("SELECT * FROM usuarios WHERE id=?", (app.config['LOCAL_ACTOR_ID'],)).fetchone()
        elif session.get("usuario_id"):
            g.usuario = get_db().execute("SELECT * FROM usuarios WHERE id=? AND ativo=1", (session["usuario_id"],)).fetchone()
            if g.usuario is None: session.clear()
        if request.method in {"POST","PUT","PATCH","DELETE"}:
            token = request.form.get("csrf_token", "")
            if not token or not hmac.compare_digest(session.get("csrf_token", ""), token):
                abort(400, description="Token de segurança inválido ou expirado.")

    @app.context_processor
    def template_globals():
        return {"csrf_token":session.get("csrf_token",""),"usuario_atual":g.get("usuario"),
                "status_opcoes":STATUS,"prioridade_opcoes":PRIORIDADES,"perfil_opcoes":PERFIS,"hoje":date.today().isoformat()}

    @app.template_filter("data_br")
    def data_br(value):
        if not value: return "—"
        try: return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
        except ValueError: return str(value)

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.usuario is None: return redirect(url_for("login", proximo=request.full_path.rstrip("?")))
            return view(*args, **kwargs)
        return wrapped

    def role_required(*roles):
        def decorator(view):
            @wraps(view)
            @login_required
            def wrapped(*args, **kwargs):
                if g.usuario["perfil"] not in roles: abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorator

    def value(name, label, minimum, maximum, required=True):
        result = request.form.get(name, "").strip()
        if required and not result:
            flash(f"O campo {label} é obrigatório.", "error"); return None
        if result and not minimum <= len(result) <= maximum:
            flash(f"{label.capitalize()} deve ter entre {minimum} e {maximum} caracteres.", "error"); return None
        return result

    def user_id(raw):
        if not raw: return None
        if not re.fullmatch(r"[0-9]{1,18}", raw): return False
        found = get_db().execute("SELECT id FROM usuarios WHERE id=? AND ativo=1 AND email != 'operacao-local@sgdi.invalid'", (int(raw),)).fetchone()
        return int(raw) if found else False

    def demand_or_404(demand_id):
        row = get_db().execute("""SELECT d.*, r.nome responsavel_nome, c.nome criador_nome, s.nome solicitante_nome, s.email solicitante_email FROM demandas d
          LEFT JOIN usuarios r ON r.id=d.responsavel_id LEFT JOIN usuarios s ON s.id=d.solicitante_id LEFT JOIN usuarios c ON c.id=d.criado_por_id WHERE d.id=?""", (demand_id,)).fetchone()
        if row is None: abort(404)
        return row

    def responsaveis(current=None, include_inactive=False):
        return get_db().execute("""SELECT id,nome,ativo FROM usuarios
            WHERE email != 'operacao-local@sgdi.invalid'
            AND ((ativo=1 AND perfil IN ('administrador','gestor','colaborador')) OR id=? OR ?)
            ORDER BY nome COLLATE NOCASE,id""", (current, include_inactive)).fetchall()

    def solicitantes(current=None, include_inactive=False):
        return get_db().execute("SELECT id,nome,email,ativo FROM usuarios WHERE email != 'operacao-local@sgdi.invalid' AND (ativo=1 OR id=? OR ?) ORDER BY nome COLLATE NOCASE,id", (current, include_inactive)).fetchall()

    @app.get("/relatorios/solicitantes")
    @login_required
    def relatorio_solicitantes():
        rows = get_db().execute("""SELECT u.id,u.nome,u.email,u.ativo,COUNT(d.id) total,
          COALESCE(SUM(d.status='aberta'),0) abertas,
          COALESCE(SUM(d.status IN ('aberta','em_analise','em_andamento','aguardando')),0) em_aberto,
          COALESCE(SUM(d.status='concluida'),0) concluidas,
          COALESCE(SUM(d.status='cancelada'),0) canceladas
          FROM usuarios u LEFT JOIN demandas d ON d.solicitante_id=u.id
          WHERE u.email != 'operacao-local@sgdi.invalid'
          GROUP BY u.id ORDER BY u.nome COLLATE NOCASE,u.id""").fetchall()
        pending = get_db().execute("SELECT COUNT(*) FROM demandas WHERE solicitante_id IS NULL").fetchone()[0]
        return render_template("relatorio_solicitantes.html", registros=rows, pendentes=pending)

    def audit(db, demand_id, action, details=None):
        db.execute("INSERT INTO historico(demanda_id,usuario_id,acao,detalhes,data) VALUES (?,?,?,?,?)",
                   (demand_id,g.usuario["id"],action,details,datetime.now().isoformat(" ","seconds")))

    def safe_next(target):
        parsed = urlsplit(target or "")
        return target if not parsed.netloc and parsed.path.startswith("/") and not parsed.path.startswith("//") else url_for("dashboard")

    @app.route("/login", methods=["GET","POST"])
    def login():
        if g.usuario: return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = value("email","e-mail",5,254); password = request.form.get("senha","")
            user = get_db().execute("SELECT * FROM usuarios WHERE email=? AND ativo=1", ((email or "").lower(),)).fetchone()
            if user and check_password_hash(user["senha_hash"],password):
                target = safe_next(request.form.get("proximo")); session.clear()
                session["usuario_id"] = user["id"]; session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(target)
            flash("E-mail ou senha inválidos.","error")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout(): session.clear(); return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard():
        db = get_db()
        totals = db.execute("""SELECT COUNT(*) total, COALESCE(SUM(status='aberta'),0) abertas,
          COALESCE(SUM(status='em_andamento'),0) em_andamento, COALESCE(SUM(status='concluida'),0) concluidas,
          COALESCE(SUM(prazo<date('now') AND status NOT IN ('concluida','cancelada')),0) atrasadas FROM demandas""").fetchone()
        recent = db.execute("""SELECT d.*,u.nome responsavel_nome FROM demandas d LEFT JOIN usuarios u ON u.id=d.responsavel_id
          ORDER BY d.data_atualizacao DESC,d.id DESC LIMIT 6""").fetchall()
        return render_template("dashboard.html",totais=totals,recentes=recent,
          por_status=db.execute("SELECT status,COUNT(*) total FROM demandas GROUP BY status").fetchall(),
          por_prioridade=db.execute("SELECT prioridade,COUNT(*) total FROM demandas GROUP BY prioridade").fetchall())

    @app.get("/demandas")
    @login_required
    def index():
        q=request.args.get("q", "").strip()[:200]
        status=request.args.get("status", "")
        priority=request.args.get("prioridade", "")
        responsible=request.args.get("responsavel", "")
        requester=request.args.get("solicitante", "")
        sort=request.args.get("ordenar", "recentes")
        sort=sort if sort in SORTS else "recentes"
        if status and status not in STATUS: abort(400, description="Filtro de status inválido.")
        if priority and priority not in PRIORIDADES: abort(400, description="Filtro de prioridade inválido.")
        try: page=max(1,int(request.args.get("pagina", "1")))
        except ValueError: page=1
        try: per_page=int(request.args.get("por_pagina", app.config['PER_PAGE']))
        except ValueError: per_page=app.config['PER_PAGE']
        if per_page not in (10,25,50,app.config['PER_PAGE']): per_page=app.config['PER_PAGE']
        conditions=[]; params=[]
        if q:
            conditions.append("(d.titulo LIKE ? ESCAPE '\\' OR d.descricao LIKE ? ESCAPE '\\' OR COALESCE(s.nome,d.solicitante) LIKE ? ESCAPE '\\' OR CAST(d.id AS TEXT)=?)")
            escaped=q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
            params += [f"%{escaped}%"]*3+[q]
        if status: conditions.append("d.status=?"); params.append(status)
        if priority: conditions.append("d.prioridade=?"); params.append(priority)
        if responsible == 'sem': conditions.append('d.responsavel_id IS NULL')
        elif re.fullmatch(r"[0-9]{1,18}", responsible): conditions.append('d.responsavel_id=?'); params.append(int(responsible))
        elif responsible: abort(400, description="Filtro de responsável inválido.")
        if requester == 'pendente': conditions.append('d.solicitante_id IS NULL')
        elif re.fullmatch(r"[0-9]{1,18}", requester): conditions.append('d.solicitante_id=?'); params.append(int(requester))
        elif requester: abort(400, description="Solicitante inválido.")
        where=' WHERE '+' AND '.join(conditions) if conditions else ''
        db=get_db()
        joins=' FROM demandas d LEFT JOIN usuarios s ON s.id=d.solicitante_id LEFT JOIN usuarios u ON u.id=d.responsavel_id'
        total=db.execute('SELECT COUNT(*)'+joins+where,params).fetchone()[0]
        pages=max(1,(total+per_page-1)//per_page); page=min(page,pages)
        rows=db.execute('SELECT d.*,u.nome responsavel_nome,s.nome solicitante_nome'+joins+where+
            f' ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?',(*params,per_page,(page-1)*per_page)).fetchall()
        query=dict(q=q,status=status,prioridade=priority,responsavel=responsible,solicitante=requester,ordenar=sort,por_pagina=per_page)
        page_url=lambda number: url_for('index',**query,pagina=number)
        return render_template('index.html',demandas=rows,total=total,pagina=page,paginas=pages,termo=q,
            filtro_status=status,filtro_prioridade=priority,filtro_responsavel=responsible,filtro_solicitante=requester,
            ordenar=sort,responsaveis=responsaveis(include_inactive=True),solicitantes=solicitantes(include_inactive=True),
            por_pagina=per_page,inicio=(page-1)*per_page+1 if total else 0,fim=min(page*per_page,total),
            page_url=page_url,query=query,page_numbers=range(max(1,page-2),min(pages,page+2)+1))

    def demand_form(current=None, current_responsible=None):
        title=value("titulo","título",3,200); description=value("descricao","descrição",3,5000)
        raw_requester=request.form.get("solicitante_id", "")
        requester=user_id(raw_requester)
        if current is not None and raw_requester == str(current): requester=current
        if requester is None or requester is False:
            flash("Selecione um solicitante cadastrado e ativo.", "error"); requester=None
        status=request.form.get("status","aberta")
        priority=request.form.get("prioridade","media"); responsible=user_id(request.form.get("responsavel_id",""))
        if current_responsible is not None and request.form.get("responsavel_id") == str(current_responsible):
            responsible=current_responsible
        deadline=request.form.get("prazo","").strip() or None
        if status not in STATUS: flash("Status inválido.","error"); status=None
        if priority not in PRIORIDADES: flash("Prioridade inválida.","error"); priority=None
        if responsible is False: flash("Responsável inválido.","error")
        try:
            if deadline: date.fromisoformat(deadline)
        except ValueError: flash("Prazo inválido.","error"); deadline=False
        return title,description,requester,status,priority,responsible,deadline

    def valid_demand_form(form):
        return all(item is not None for item in form[:5]) and form[5] is not False and form[6] is not False

    @app.route("/nova_demanda", methods=["GET","POST"])
    @app.route("/demandas/nova", methods=["GET","POST"])
    @role_required("administrador","gestor","colaborador")
    def nova_demanda():
        if request.method == "POST":
            form=demand_form()
            if valid_demand_form(form):
                db=get_db(); now=datetime.now().isoformat(" ","seconds")
                cursor=db.execute("""INSERT INTO demandas(titulo,descricao,solicitante_id,status,prioridade,responsavel_id,prazo,solicitante,criado_por_id,data_criacao,data_atualizacao)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""",(*form,db.execute("SELECT nome FROM usuarios WHERE id=?", (form[2],)).fetchone()[0],g.usuario["id"],now,now))
                audit(db,cursor.lastrowid,"Demanda criada",f"Solicitante ID: {form[2]}; status: {STATUS[form[3]]}; prioridade: {PRIORIDADES[form[4]]}")
                db.commit(); flash("Demanda criada com sucesso.","success")
                return redirect(url_for("detalhes",demanda_id=cursor.lastrowid))
        return render_template("nova_demanda.html",responsaveis=responsaveis(),solicitantes=solicitantes())

    @app.route("/editar/<int:demanda_id>",methods=["GET","POST"])
    @app.route("/demandas/<int:demanda_id>/editar",methods=["GET","POST"])
    @role_required("administrador","gestor")
    def editar(demanda_id):
        demand=demand_or_404(demanda_id)
        if request.method == "POST":
            form=demand_form(demand["solicitante_id"], demand["responsavel_id"])
            if valid_demand_form(form):
                labels=("Título","Descrição","Solicitante","Status","Prioridade","Responsável","Prazo")
                old=(demand["titulo"],demand["descricao"],demand["solicitante_id"],demand["status"],demand["prioridade"],demand["responsavel_id"],demand["prazo"])
                changes=[f"{label} alterado" for label,a,b in zip(labels,old,form) if a!=b]
                db=get_db(); now=datetime.now().isoformat(" ","seconds")
                if demand["solicitante_id"] != form[2]:
                    changes.append(f"Solicitante ID: {demand['solicitante_id'] or 'pendente'} -> {form[2]}")
                db.execute("""UPDATE demandas SET titulo=?,descricao=?,solicitante_id=?,status=?,prioridade=?,responsavel_id=?,prazo=?,solicitante=?,data_atualizacao=? WHERE id=?""",(*form,db.execute("SELECT nome FROM usuarios WHERE id=?", (form[2],)).fetchone()[0],now,demanda_id))
                audit(db,demanda_id,"Demanda atualizada","; ".join(changes) or "Formulário salvo sem alterações")
                db.commit(); flash("Demanda atualizada com sucesso.","success")
                return redirect(url_for("detalhes",demanda_id=demanda_id))
        return render_template("editar.html",demanda=demand,responsaveis=responsaveis(demand["responsavel_id"]),solicitantes=solicitantes(demand["solicitante_id"]))

    @app.get("/detalhes/<int:demanda_id>")
    @app.get("/demandas/<int:demanda_id>")
    @login_required
    def detalhes(demanda_id):
        demand=demand_or_404(demanda_id); db=get_db()
        comments=db.execute("SELECT * FROM comentarios WHERE demanda_id=? ORDER BY data,id",(demanda_id,)).fetchall()
        history=db.execute("""SELECT h.*,u.nome usuario_nome FROM historico h LEFT JOIN usuarios u ON u.id=h.usuario_id
          WHERE h.demanda_id=? ORDER BY h.data DESC,h.id DESC""",(demanda_id,)).fetchall()
        return render_template("detalhes.html",demanda=demand,comentarios=comments,historico=history)

    @app.post("/adicionar_comentario/<int:demanda_id>")
    @app.post("/demandas/<int:demanda_id>/comentarios")
    @role_required("administrador","gestor","colaborador")
    def adicionar_comentario(demanda_id):
        demand_or_404(demanda_id); comment=value("comentario","comentário",1,5000)
        if comment:
            db=get_db(); now=datetime.now().isoformat(" ","seconds")
            db.execute("INSERT INTO comentarios(demanda_id,comentario,autor,usuario_id,data) VALUES (?,?,?,?,?)",(demanda_id,comment,g.usuario["nome"],g.usuario["id"],now))
            audit(db,demanda_id,"Comentário adicionado"); db.execute("UPDATE demandas SET data_atualizacao=? WHERE id=?",(now,demanda_id)); db.commit()
            flash("Comentário adicionado.","success")
        return redirect(url_for("detalhes",demanda_id=demanda_id))

    @app.post("/deletar/<int:demanda_id>")
    @app.post("/demandas/<int:demanda_id>/excluir")
    @role_required("administrador")
    def deletar(demanda_id):
        demand_or_404(demanda_id); db=get_db(); db.execute("DELETE FROM demandas WHERE id=?",(demanda_id,)); db.commit()
        flash("Demanda excluída.","success"); return redirect(url_for("index"))

    @app.route("/usuarios",methods=["GET","POST"])
    @role_required("administrador")
    def usuarios():
        db=get_db()
        if request.method == "POST":
            name=value("nome","nome",2,120); email=value("email","e-mail",5,254); password=request.form.get("senha","") if app.config["AUTH_REQUIRED"] else secrets.token_urlsafe(32); role=request.form.get("perfil","")
            if email and not EMAIL_RE.fullmatch(email): flash("E-mail inválido.","error"); email=None
            if len(password)<12: flash("A senha deve ter pelo menos 12 caracteres.","error")
            elif role not in PERFIS: flash("Perfil inválido.","error")
            elif name and email:
                try:
                    db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES (?,?,?,?)",(name,email.lower(),generate_password_hash(password),role)); db.commit()
                    flash("Usuário criado com sucesso.","success"); return redirect(url_for("usuarios"))
                except sqlite3.IntegrityError: flash("Já existe um usuário com esse e-mail.","error")
        return render_template("usuarios.html",usuarios=db.execute("SELECT * FROM usuarios WHERE email != 'operacao-local@sgdi.invalid' ORDER BY ativo DESC,nome COLLATE NOCASE").fetchall())

    @app.post("/usuarios/<int:usuario_id>/alternar")
    @role_required("administrador")
    def alternar_usuario(usuario_id):
        target=get_db().execute("SELECT * FROM usuarios WHERE id=?",(usuario_id,)).fetchone()
        if not target: abort(404)
        if usuario_id==g.usuario["id"]: flash("Você não pode desativar sua própria conta.","error")
        else:
            db=get_db(); db.execute("UPDATE usuarios SET ativo=CASE ativo WHEN 1 THEN 0 ELSE 1 END WHERE id=?",(usuario_id,)); db.commit(); flash("Situação atualizada.","success")
        return redirect(url_for("usuarios"))

    @app.errorhandler(400)
    def bad_request(error): return render_template("error.html",codigo=400,titulo="Requisição inválida",mensagem=getattr(error,"description","Não foi possível processar a solicitação.")),400
    @app.errorhandler(403)
    def forbidden(_error): return render_template("error.html",codigo=403,titulo="Acesso negado",mensagem="Seu perfil não tem permissão para esta ação."),403
    @app.errorhandler(404)
    def not_found(_error): return render_template("404.html"),404
    @app.errorhandler(500)
    def server_error(_error):
        db=g.pop("db",None)
        if db is not None: db.rollback(); db.close()
        return render_template("500.html"),500
    return app

if __name__ == "__main__":
    application=create_app()
    application.run(host=os.environ.get("HOST","127.0.0.1"),port=int(os.environ.get("PORT","5050")),debug=False)
