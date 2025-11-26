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
import pytz  # <<< timezone Brasil

# --------------------------------------------------------------------------- #
#                          Configuração inicial
# --------------------------------------------------------------------------- #

load_dotenv()

app = Flask(__name__)

# Timezone Brasil
BR_TZ = pytz.timezone("America/Sao_Paulo")

# Caminho do .env (para salvar dados da escola)
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

# --- Configuração básica / segredos -----------------------------------------
app.secret_key = os.getenv("SECRET_KEY", "mude_esta_chave_super_secreta")

# Usuário e senha da Central vindos das variáveis de ambiente
CENTRAL_USER = os.getenv("CENTRAL_USER", "central")
CENTRAL_PASS = os.getenv("CENTRAL_PASS", "1234")

# --- Dados da Escola (para relatório / telas) ------------------------------- #
SCHOOL_NAME = os.getenv("SCHOOL_NAME", "Escola Modelo PROF-SAFE 24")
SCHOOL_ADDRESS = os.getenv("SCHOOL_ADDRESS", "Endereço não configurado")
SCHOOL_CONTACT = os.getenv("SCHOOL_CONTACT", "Telefone/E-mail não configurados")
SCHOOL_DIRECTOR = os.getenv("SCHOOL_DIRECTOR", "Direção não configurada")

# Bloco em memória editável via /admin/escola
SCHOOL_DATA = {
    "nome": SCHOOL_NAME,
    "endereco": SCHOOL_ADDRESS,
    "telefone": SCHOOL_CONTACT,
    "diretor": SCHOOL_DIRECTOR,
}

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


def save_school_to_env(school: dict) -> None:
    """
    Atualiza/insere SCHOOL_NAME, SCHOOL_ADDRESS, SCHOOL_CONTACT, SCHOOL_DIRECTOR no .env.
    (Em alguns ambientes de hospedagem o .env pode não ser persistente, mas local funciona.)
    """
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

        env_data["SCHOOL_NAME"] = school.get("nome", "")
        env_data["SCHOOL_ADDRESS"] = school.get("endereco", "")
        env_data["SCHOOL_CONTACT"] = school.get("telefone", "")
        env_data["SCHOOL_DIRECTOR"] = school.get("diretor", "")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            for k, v in env_data.items():
                f.write(f"{k}={v}\n")

        app.logger.info("[ADMIN] .env atualizado com dados da escola.")

    except Exception as e:
        app.logger.error(f"[ADMIN] Erro ao salvar .env: {e}")


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
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


# ------------------------- ROTA /admin/escola ------------------------------- #
@app.route("/admin/escola", methods=["GET", "POST"])
def admin_escola():
    """
    Tela para editar os dados da escola em memória + salvar no .env.
    """
    global SCHOOL_DATA, SCHOOL_NAME, SCHOOL_ADDRESS, SCHOOL_CONTACT, SCHOOL_DIRECTOR

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip() or SCHOOL_DATA["nome"]
        endereco = (request.form.get("endereco") or "").strip() or SCHOOL_DATA["endereco"]
        telefone = (request.form.get("telefone") or "").strip() or SCHOOL_DATA["telefone"]
        diretor = (request.form.get("diretor") or "").strip() or SCHOOL_DATA["diretor"]

        SCHOOL_DATA["nome"] = nome
        SCHOOL_DATA["endereco"] = endereco
        SCHOOL_DATA["telefone"] = telefone
        SCHOOL_DATA["diretor"] = diretor

        # Atualiza também as variáveis usadas no PDF
        SCHOOL_NAME = nome
        SCHOOL_ADDRESS = endereco
        SCHOOL_CONTACT = telefone
        SCHOOL_DIRECTOR = diretor

        # Tenta gravar no .env
        save_school_to_env(SCHOOL_DATA)

        app.logger.info(
            f"[ADMIN] Dados da escola atualizados: "
            f"{nome} / {endereco} / {telefone} / {diretor}"
        )
        return redirect(url_for("admin_escola"))

    return render_template("admin_school.html", escola=SCHOOL_DATA)


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

    # Horário Brasil
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
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle("Relatório PROF-SAFE 24")

    # Pega os dados atuais da escola
    nome_escola = SCHOOL_DATA.get("nome", SCHOOL_NAME)
    endereco_escola = SCHOOL_DATA.get("endereco", SCHOOL_ADDRESS)
    contato_escola = SCHOOL_DATA.get("telefone", SCHOOL_CONTACT)

    # Cabeçalho
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 800, "PROF-SAFE 24 - Relatório de Alertas")

    pdf.setFont("Helvetica", 10)
    y = 780
    pdf.drawString(40, y, f"Escola: {nome_escola}")
    y -= 12
    pdf.drawString(40, y, f"Endereço: {endereco_escola}")
    y -= 12
    pdf.drawString(40, y, f"Contato: {contato_escola}")
    y -= 12

    # Horário de geração em BRT
    data_geracao = datetime.now(BR_TZ).strftime("%d/%m/%Y %H:%M:%S")
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
