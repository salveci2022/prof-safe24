from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
)
from datetime import datetime
import os

# Se seus HTMLs estiverem na pasta "templates" e os arquivos estáticos na "static"
app = Flask(__name__, template_folder="templates", static_folder="static")

# Chave de sessão (para login da central)
app.secret_key = os.environ.get("SECRET_KEY", "spynet-secret-key")

# Credenciais da central (pode mudar via variável de ambiente no Render)
ADMIN_USER = os.environ.get("ADMIN_USER", "central")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "1234")

# =========================
# ESTADO EM MEMÓRIA
# (suficiente para demonstração)
# =========================

alerts = []        # lista de dicionários: {teacher, room, description, ts, resolved}
siren_on = False   # True = sirene ligada
siren_muted = False  # já deixo pronto caso queira usar depois


# =========================
# ROTAS DE PÁGINA (HTML)
# =========================

@app.route("/")
def home():
    # Tela inicial SPYNET (home.html)
    return render_template("home.html")


@app.route("/professor")
def professor():
    # App do Professor (professor.html)
    return render_template("professor.html")


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    """
    Tela de login para a Central.
    O formulário de login_central.html faz POST para esta mesma rota. :contentReference[oaicite:10]{index=10}
    """
    error = None

    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        senha = (request.form.get("senha") or "").strip()

        if usuario == ADMIN_USER and senha == ADMIN_PASS:
            session["central_logged"] = True
            return redirect(url_for("central"))
        else:
            # Mesmo que o HTML não exiba erro, já deixo pronto
            error = "Usuário ou senha inválidos."

    return render_template("login_central.html", error=error)


@app.route("/central")
def central():
    """
    Painel Central – só acessa se estiver logado.
    O home.html redireciona para /login_central primeiro. :contentReference[oaicite:11]{index=11}
    """
    if not session.get("central_logged"):
        return redirect(url_for("login_central"))
    return render_template("central.html")


@app.route("/admin")
def admin():
    # Área administrativa (admin.html) – resumo bonito para diretores. :contentReference[oaicite:12]{index=12}
    return render_template("admin.html")


@app.route("/painel_publico")
def painel_publico():
    """
    Painel público para TV/corredor, que consome /api/status via fetch(). :contentReference[oaicite:13]{index=13}
    """
    return render_template("painel_publico.html")


# =========================
# ROTAS DE API (JSON)
# =========================

@app.route("/api/alert", methods=["POST"])
def api_alert():
    """
    Recebe alerta enviado pelo professor.
    O professor.html faz:
    fetch('/api/alert', { method:'POST', body: JSON.stringify({ teacher, room, description }) })
    e espera { ok: true/false, message: '...' }. :contentReference[oaicite:14]{index=14}
    """
    global siren_on

    data = request.get_json() or {}
    teacher = data.get("teacher") or "Professor"
    room = (data.get("room") or "").strip()
    description = (data.get("description") or "").strip()

    if not room or not description:
        return jsonify({
            "ok": False,
            "message": "Sala e descrição são obrigatórias."
        }), 400

    alert = {
        "teacher": teacher,
        "room": room,
        "description": description,
        "ts": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "resolved": False,
    }
    alerts.append(alert)

    # Ativa a sirene no painel central
    siren_on = True

    return jsonify({
        "ok": True,
        "message": "Alerta recebido com sucesso pela Central."
    })


@app.route("/api/status", methods=["GET"])
def api_status():
    """
    Usado pelo Painel Central e pelo Painel Público para ler:
    - lista de alertas
    - estado da sirene (ligada/desligada)
    - flag de mudo (já deixo no JSON para futura expansão). :contentReference[oaicite:15]{index=15} :contentReference[oaicite:16]{index=16}
    """
    return jsonify({
        "alerts": alerts,
        "siren": siren_on,
        "muted": siren_muted,
    })


@app.route("/api/siren", methods=["POST"])
def api_siren():
    """
    Controle da sirene vindo do Painel Central.
    O central.html chama siren('on') e siren('off'). :contentReference[oaicite:17]{index=17}
    """
    global siren_on

    data = request.get_json() or {}
    action = data.get("action")

    if action == "on":
        siren_on = True
    elif action == "off":
        siren_on = False

    return jsonify({
        "ok": True,
        "siren": siren_on
    })


@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    """
    Marca o PRÓXIMO alerta pendente como resolvido.
    O Painel Central chama esta rota ao clicar em "RESOLVER ALERTA". :contentReference[oaicite:18]{index=18}
    """
    global siren_on

    for alert in alerts:
        if not alert.get("resolved"):
            alert["resolved"] = True
            break

    # Se não sobrou nenhum alerta ativo, pode desligar a sirene
    if not any(not a.get("resolved") for a in alerts):
        siren_on = False

    return jsonify({"ok": True})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """
    Limpa TODOS os alertas (botão LIMPAR FEED no Painel Central). :contentReference[oaicite:19]{index=19}
    """
    global alerts, siren_on
    alerts = []
    siren_on = False
    return jsonify({"ok": True})


# =========================
# MAIN – para rodar no Render com python app.py
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
