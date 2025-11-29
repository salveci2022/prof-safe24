import os
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
)
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
import pytz  # timezone Brasil

# --------------------------------------------------------------------------- #
#                          Configuração inicial
# --------------------------------------------------------------------------- #

load_dotenv()

app = Flask(__name__)

# Timezone Brasil
BR_TZ = pytz.timezone("America/Sao_Paulo")

# Caminho do .env
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

# Chave de sessão
app.secret_key = os.getenv("SECRET_KEY", "mude_esta_chave_super_secreta")

# Usuário da central
CENTRAL_USER = os.getenv("CENTRAL_USER", "central")
CENTRAL_PASS = os.getenv("CENTRAL_PASS", "1234")

# Dados da escola
SCHOOL_NAME = os.getenv("SCHOOL_NAME", "Escola Modelo PROF-SAFE 24")
SCHOOL_ADDRESS = os.getenv("SCHOOL_ADDRESS", "Endereço não configurado")
SCHOOL_CONTACT = os.getenv("SCHOOL_CONTACT", "Telefone/E-mail não configurados")

# Controle de segurança
MAX_LOGIN_ATTEMPTS = 5
LOCK_TIME_MINUTES = 10
SESSION_TIMEOUT_MINUTES = 15
login_attempts = {}

alerts = []
siren_on = False
muted = False


# --------------------------------------------------------------------------- #
#                            Funções utilitárias
# --------------------------------------------------------------------------- #

def get_client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


def is_ip_locked(ip: str) -> bool:
    data = login_attempts.get(ip)
    if not data:
        return False

    locked_until = data.get("locked_until")
    if locked_until and datetime.utcnow() < locked_until:
        return True

    if locked_until and datetime.utcnow() >= locked_until:
        login_attempts.pop(ip, None)
        return False

    return False


def register_failed_login(ip: str) -> None:
    now = datetime.utcnow()
    record = login_attempts.get(ip, {"count": 0, "locked_until": None})
    record["count"] += 1

    if record["count"] >= MAX_LOGIN_ATTEMPTS:
        record["locked_until"] = now + timedelta(minutes=LOCK_TIME_MINUTES)

    login_attempts[ip] = record


def reset_login_attempts(ip: str) -> None:
    if ip in login_attempts:
        login_attempts.pop(ip, None)


def save_school_to_env(name: str, address: str, contact: str) -> None:
    try:
        env_data = {}

        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env_data[k.strip()] = v.strip()

        env_data["SCHOOL_NAME"] = name
        env_data["SCHOOL_ADDRESS"] = address
        env_data["SCHOOL_CONTACT"] = contact

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            for k, v in env_data.items():
                f.write(f"{k}={v}\n")

    except Exception as e:
        print(f"Erro ao salvar .env: {e}")


# --------------------------------------------------------------------------- #
#                       Controle de sessão / timeout
# --------------------------------------------------------------------------- #

@app.before_request
def enforce_session_timeout():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    if session.get("central_logged"):
        last_seen = session.get("last_seen")
        now_ts = datetime.utcnow().timestamp()

        if last_seen is not None:
            elapsed_seconds = now_ts - float(last_seen)
            if elapsed_seconds > SESSION_TIMEOUT_MINUTES * 60:
                session.clear()
                return redirect(url_for("login_central"))

        session["last_seen"] = now_ts


# --------------------------------------------------------------------------- #
#                                   Rotas
# --------------------------------------------------------------------------- #

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


# --------------------------------------------------------------------------- #
#                   ROTA COMPLETA DO CADASTRO DA ESCOLA
# --------------------------------------------------------------------------- #

@app.route("/admin/escola", methods=["GET", "POST"])
def admin_escola_painel():
    global SCHOOL_NAME, SCHOOL_ADDRESS, SCHOOL_CONTACT

    saved = False

    if request.method == "POST":
        SCHOOL_NAME = request.form.get("school_name", "").strip()
        SCHOOL_ADDRESS = request.form.get("school_address", "").strip()
        SCHOOL_CONTACT = request.form.get("school_contact", "").strip()

        save_school_to_env(SCHOOL_NAME, SCHOOL_ADDRESS, SCHOOL_CONTACT)
        saved = True

    return render_template(
        "admin_school.html",
        school_name=SCHOOL_NAME,
        school_address=SCHOOL_ADDRESS,
        school_contact=SCHOOL_CONTACT,
        saved=saved
    )


# --------------------------------------------------------------------------- #
#                         LOGIN DA CENTRAL
# --------------------------------------------------------------------------- #

@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    client_ip = get_client_ip()
    error = None

    if is_ip_locked(client_ip):
        error = "Muitas tentativas deste IP. Tente mais tarde."
        return render_template("login_central.html", error=error)

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()

        if usuario == CENTRAL_USER and senha == CENTRAL_PASS:
            reset_login_attempts(client_ip)
            session["central_logged"] = True
            session["central_user"] = usuario
            session["last_seen"] = datetime.utcnow().timestamp()
            return redirect(url_for("central"))
        else:
            register_failed_login(client_ip)
            error = "Usuário ou senha inválidos."

    return render_template("login_central.html", error=error)


@app.route("/central")
def central():
    if not session.get("central_logged"):
        return redirect(url_for("login_central"))
    return render_template("central.html")


@app.route("/logout_central")
def logout_central():
    session.clear()
    return redirect(url_for("home"))


# --------------------------------------------------------------------------- #
#                        API – ALERTAS / SIRENE
# --------------------------------------------------------------------------- #

@app.route("/api/alert", methods=["POST"])
def api_alert():
    global alerts, siren_on, muted

    data = request.get_json(silent=True) or {}
    teacher = (data.get("teacher") or "").strip()
    room = (data.get("room") or "").strip()
    description = (data.get("description") or "").strip()

    if not room or not description:
        return jsonify({"ok": False}), 400

    ts = datetime.now(BR_TZ).strftime("%d/%m/%Y %H:%M:%S")

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

    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    return jsonify({"ok": True, "alerts": alerts, "siren": siren_on, "muted": muted})


@app.route("/api/siren", methods=["POST"])
def api_siren():
    global siren_on, muted
    action = (request.get_json(silent=True) or {}).get("action", "").lower()

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

    return jsonify({"ok": True})


@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    for a in alerts:
        if not a["resolved"]:
            a["resolved"] = True
            break
    return jsonify({"ok": True})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    global alerts, siren_on, muted
    alerts = []
    siren_on = False
    muted = False
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
#                        PDF – RELATÓRIO
# --------------------------------------------------------------------------- #

@app.route("/report.pdf")
def report_pdf():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle("Relatório PROF-SAFE 24")

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 800, "PROF-SAFE 24 - Relatório de Alertas")

    pdf.setFont("Helvetica", 10)
    y = 780
    pdf.drawString(40, y, f"Escola: {SCHOOL_NAME}")
    y -= 12
    pdf.drawString(40, y, f"Endereço: {SCHOOL_ADDRESS}")
    y -= 12
    pdf.drawString(40, y, f"Contato: {SCHOOL_CONTACT}")
    y -= 12

    pdf.drawString(40, y, f"Gerado em: {datetime.now(BR_TZ).strftime('%d/%m/%Y %H:%M:%S')}")
    y -= 24

    pdf.setFont("Helvetica", 10)

    if not alerts:
        pdf.drawString(40, y, "Nenhum alerta registrado até o momento.")
    else:
        for idx, a in enumerate(alerts, start=1):
            if y < 80:
                pdf.showPage()
                y = 800
                pdf.setFont("Helvetica", 10)

            pdf.drawString(40, y, f"{idx}. Prof: {a['teacher']} Sala: {a['room']}")
            y -= 14
            pdf.drawString(
                40, y,
                f"   Data/Hora: {a['ts']}  Status: {'Resolvido' if a['resolved'] else 'Ativo'}"
            )
            y -= 14
            pdf.drawString(40, y, f"   Descrição: {a['description']}")
            y -= 20

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, download_name="relatorio_prof_safe24.pdf", mimetype="application/pdf")


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
