import os
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    send_file,
    g,
)
from dotenv import load_dotenv
from reportlab.pdfgen import canvas

load_dotenv()

app = Flask(__name__)

# --- Configuração básica / segredos -----------------------------------------
app.secret_key = os.getenv("SECRET_KEY", "mude_esta_chave_super_secreta")

# Usuário e senha da Central vindos das variáveis de ambiente
CENTRAL_USER = os.getenv("CENTRAL_USER", "central")
CENTRAL_PASS = os.getenv("CENTRAL_PASS", "1234")

# --- Dados da Escola (defaults / fallback) ----------------------------------
SCHOOL_NAME = os.getenv("SCHOOL_NAME", "Escola Modelo PROF-SAFE 24")
SCHOOL_ADDRESS = os.getenv("SCHOOL_ADDRESS", "Endereço não configurado")
SCHOOL_CONTACT = os.getenv("SCHOOL_CONTACT", "Telefone/E-mail não configurados")

# --- Banco de dados (SQLite simples) ----------------------------------------
DATABASE = "prof_safe24.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS school (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            endereco TEXT,
            contato TEXT,
            diretor TEXT
        )
        """
    )
    # registro único padrão da escola (id = 1)
    db.execute(
        """
        INSERT OR IGNORE INTO school (id, nome, endereco, contato, diretor)
        VALUES (1, ?, ?, ?, ?)
        """,
        (SCHOOL_NAME, SCHOOL_ADDRESS, SCHOOL_CONTACT, "Direção não cadastrada"),
    )
    db.commit()


with app.app_context():
    init_db()

# --- Segurança: limites de login e sessão -----------------------------------
MAX_LOGIN_ATTEMPTS = 5          # tentativas máximas antes de bloquear
LOCK_TIME_MINUTES = 10          # tempo de bloqueio do IP
SESSION_TIMEOUT_MINUTES = 15    # tempo de inatividade até deslogar

# ip -> {"count": int, "locked_until": datetime}
login_attempts = {}

# --------------------------------------------------------------------------- #
#                               Funções utilitárias
# --------------------------------------------------------------------------- #
def get_client_ip() -> str:
    """
    Pega o IP real do cliente. No Render, pode vir em X-Forwarded-For.
    """
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # Pode vir "ip1, ip2, ip3" → usamos o primeiro
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


def is_ip_locked(ip: str) -> bool:
    """
    Verifica se o IP está bloqueado por muitas tentativas erradas.
    """
    data = login_attempts.get(ip)
    if not data:
        return False

    locked_until = data.get("locked_until")
    if locked_until and datetime.utcnow() < locked_until:
        return True

    # Se já passou do tempo de bloqueio, limpamos o registro
    if locked_until and datetime.utcnow() >= locked_until:
        login_attempts.pop(ip, None)
        return False

    return False


def register_failed_login(ip: str) -> None:
    """
    Registra uma tentativa de login falha e, se ultrapassar o limite,
    bloqueia o IP por LOCK_TIME_MINUTES.
    """
    now = datetime.utcnow()
    record = login_attempts.get(ip, {"count": 0, "locked_until": None})
    record["count"] += 1

    if record["count"] >= MAX_LOGIN_ATTEMPTS:
        record["locked_until"] = now + timedelta(minutes=LOCK_TIME_MINUTES)
        app.logger.warning(
            f"[SEC] IP bloqueado por muitas tentativas: {ip} "
            f"({record['count']} tentativas)"
        )

    login_attempts[ip] = record


def reset_login_attempts(ip: str) -> None:
    """
    Limpa o contador de login ao logar com sucesso.
    """
    if ip in login_attempts:
        login_attempts.pop(ip, None)


# --------------------------------------------------------------------------- #
#                      Controle de sessão / timeout automático
# --------------------------------------------------------------------------- #
@app.before_request
def enforce_session_timeout():
    """
    - Define sessão como permanente.
    - Encerra sessão da Central após SESSION_TIMEOUT_MINUTES de inatividade.
    """
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    # Só aplicamos timeout para quem está logado na Central
    if session.get("central_logged"):
        last_seen = session.get("last_seen")
        now_ts = datetime.utcnow().timestamp()

        if last_seen is not None:
            elapsed_seconds = now_ts - float(last_seen)
            if elapsed_seconds > SESSION_TIMEOUT_MINUTES * 60:
                app.logger.info(
                    f"[SEC] Sessão expirada por inatividade para usuário "
                    f"{session.get('central_user')}."
                )
                session.clear()
                return redirect(url_for("login_central"))

        # Atualiza timestamp a cada requisição
        session["last_seen"] = now_ts


# --------------------------------------------------------------------------- #
#                                   Rotas
# --------------------------------------------------------------------------- #
alerts = []
siren_on = False
muted = False


@app.route("/")
def home():
    # Busca dados da escola no banco para usar na home (se o template quiser)
    db = get_db()
    row = db.execute("SELECT * FROM school WHERE id = 1").fetchone()

    escola_nome = row["nome"] if row and row["nome"] else SCHOOL_NAME
    escola_endereco = row["endereco"] if row and row["endereco"] else SCHOOL_ADDRESS
    escola_contato = row["contato"] if row and row["contato"] else SCHOOL_CONTACT
    escola_diretor = row["diretor"] if row and row["diretor"] else "Direção não cadastrada"

    return render_template(
        "home.html",
        escola_nome=escola_nome,
        escola_endereco=escola_endereco,
        escola_telefone=escola_contato,
        escola_diretor=escola_diretor,
    )


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    error = None
    client_ip = get_client_ip()

    # 1) Verifica se o IP está bloqueado antes de tudo
    if is_ip_locked(client_ip):
        error = (
            "Muitas tentativas de acesso deste IP. "
            "Tente novamente em alguns minutos."
        )
        app.logger.warning(
            f"[SEC] Tentativa de login de IP bloqueado: {client_ip}"
        )
        return render_template("login_central.html", error=error)

    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        senha = (request.form.get("senha") or "").strip()

        # 2) Validação de credenciais
        if usuario == CENTRAL_USER and senha == CENTRAL_PASS:
            # Sucesso
            reset_login_attempts(client_ip)
            session["central_logged"] = True
            session["central_user"] = usuario
            session["last_seen"] = datetime.utcnow().timestamp()

            app.logger.info(
                f"[SEC] Login bem-sucedido na Central pelo usuário "
                f"{usuario} a partir do IP {client_ip}"
            )
            return redirect(url_for("central"))
        else:
            # Falha de login
            register_failed_login(client_ip)
            error = "Usuário ou senha inválidos."
            app.logger.warning(
                f"[SEC] Falha de login na Central. user={usuario} ip={client_ip}"
            )

    return render_template("login_central.html", error=error)


@app.route("/central")
def central():
    if not session.get("central_logged"):
        return redirect(url_for("login_central"))
    return render_template("central.html")


@app.route("/logout_central")
def logout_central():
    user = session.get("central_user")
    app.logger.info(f"[SEC] Logout manual da Central para usuário {user}")
    session.clear()
    return redirect(url_for("home"))


# -------------------------- ADMIN: Dados da Escola -------------------------- #
@app.route("/admin/escola", methods=["GET", "POST"])
def admin_escola():
    """
    Tela administrativa para configurar os dados oficiais da escola.
    Esses dados aparecem na tela inicial e no relatório em PDF.
    """
    if not session.get("central_logged"):
        # opcional: só a Central logada pode editar
        return redirect(url_for("login_central"))

    db = get_db()

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        endereco = (request.form.get("endereco") or "").strip()
        contato = (request.form.get("contato") or "").strip()
        diretor = (request.form.get("diretor") or "").strip()

        db.execute(
            """
            UPDATE school
               SET nome = ?, endereco = ?, contato = ?, diretor = ?
             WHERE id = 1
            """,
            (nome, endereco, contato, diretor),
        )
        db.commit()

        return redirect(url_for("admin_escola"))

    row = db.execute("SELECT * FROM school WHERE id = 1").fetchone()

    return render_template("admin_school.html", escola=row)


# -------------------------- API de alertas / sirene ------------------------- #
@app.route("/api/alert", methods=["POST"])
def api_alert():
    global alerts, siren_on, muted
    data = request.get_json(silent=True) or {}
    teacher = (data.get("teacher") or "").strip()
    room = (data.get("room") or "").strip()
    description = (data.get("description") or "").strip()

    if not room or not description:
        return jsonify({"ok": False}), 400

    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    alerts.insert(
        0,
        {
            "teacher": teacher,
            "room": room,
            "description": description,
            "ts": ts,
            "resolved": False,
        },
    )
    siren_on = True
    muted = False

    app.logger.info(
        f"[ALERTA] Novo alerta - Professor: {teacher} | Sala: {room} | "
        f"Descrição: {description}"
    )

    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    return jsonify({"ok": True, "alerts": alerts, "siren": siren_on, "muted": muted})


@app.route("/api/siren", methods=["POST"])
def api_siren():
    global siren_on, muted
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").lower()

    if action == "on":
        siren_on = True
        muted = False
    elif action == "off":
        siren_on = False
        muted = False
    elif action == "mute":
        siren_on = True
        muted = True
    else:
        return jsonify({"ok": False}), 400

    app.logger.info(f"[ALERTA] Sirene ação='{action}'")
    return jsonify({"ok": True})


@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    global alerts
    for a in alerts:
        if not a["resolved"]:
            a["resolved"] = True
            break
    app.logger.info("[ALERTA] Primeiro alerta marcado como resolvido.")
    return jsonify({"ok": True})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    global alerts, siren_on, muted
    alerts = []
    siren_on = False
    muted = False
    app.logger.info("[ALERTA] Todos os alertas foram limpos.")
    return jsonify({"ok": True})


# ---------------------------- Relatório em PDF ------------------------------ #
@app.route("/report.pdf")
def report_pdf():
    # Busca dados da escola no banco
    db = get_db()
    row = db.execute("SELECT * FROM school WHERE id = 1").fetchone()

    school_name = row["nome"] if row and row["nome"] else SCHOOL_NAME
    school_address = row["endereco"] if row and row["endereco"] else SCHOOL_ADDRESS
    school_contact = row["contato"] if row and row["contato"] else SCHOOL_CONTACT
    diretor = row["diretor"] if row and row["diretor"] else "Direção não cadastrada"

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle("Relatório PROF-SAFE 24")

    # Cabeçalho
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 800, "PROF-SAFE 24 - Relatório de Alertas")

    pdf.setFont("Helvetica", 10)
    y = 780
    pdf.drawString(40, y, f"Escola: {school_name}")
    y -= 12
    pdf.drawString(40, y, f"Endereço: {school_address}")
    y -= 12
    pdf.drawString(40, y, f"Contato: {school_contact}")
    y -= 12
    pdf.drawString(40, y, f"Diretor(a): {diretor}")
    y -= 12

    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pdf.drawString(40, y, f"Gerado em: {data_geracao}")
    y -= 24

    pdf.setFont("Helvetica", 10)

    # Corpo do relatório
    if not alerts:
        pdf.drawString(40, y, "Nenhum alerta registrado até o momento.")
    else:
        for idx, a in enumerate(alerts, start=1):
            if y < 80:
                pdf.showPage()
                y = 800
                pdf.setFont("Helvetica", 10)

            pdf.drawString(
                40,
                y,
                f"{idx}. Professor: {a['teacher']}  Sala: {a['room']}",
            )
            y -= 14
            pdf.drawString(
                40,
                y,
                f"   Data/Hora: {a['ts']}  "
                f"Status: {'Resolvido' if a['resolved'] else 'Ativo'}",
            )
            y -= 14
            pdf.drawString(40, y, f"   Descrição: {a['description']}")
            y -= 20

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=False,
        download_name="relatorio_prof_safe24.pdf",
        mimetype="application/pdf",
    )


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Em produção (Render) o comando é "python app.py"
    app.run(host="0.0.0.0", port=5000, debug=True)
