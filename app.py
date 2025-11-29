import os
import io
from datetime import datetime, timedelta

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
)
from reportlab.pdfgen import canvas
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ============================
# CONFIGURAÇÃO INICIAL
# ============================

CENTRAL_USER = "admin"
CENTRAL_PASS = "1234"

# Dados da escola preenchidos em /admin/escola
dados_escola = {
    "nome": "",
    "endereco": "",
    "telefone": "",
    "email": "",
    "responsavel": "",
}

# Lista de alertas e estado da sirene
alertas = []
siren_on = False


# ============================
# FUNÇÃO HORÁRIO BRASIL (UTC-3)
# ============================

def agora_brasilia():
    """Retorna datetime no fuso de Brasília (UTC-3), a partir de UTC."""
    return datetime.utcnow() - timedelta(hours=3)


# ============================
# ROTAS PÁGINAS
# ============================

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/admin/escola", methods=["GET", "POST"])
def admin_escola():
    global dados_escola
    if request.method == "POST":
        dados_escola["nome"] = request.form.get("nome", "")
        dados_escola["endereco"] = request.form.get("endereco", "")
        dados_escola["telefone"] = request.form.get("telefone", "")
        dados_escola["email"] = request.form.get("email", "")
        dados_escola["responsavel"] = request.form.get("responsavel", "")
        return redirect("/admin")

    return render_template("admin_school.html", escola=dados_escola)


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    if request.method == "POST":
        user = request.form.get("usuario", "")
        pw = request.form.get("senha", "")
        if user == CENTRAL_USER and pw == CENTRAL_PASS:
            return redirect("/central")
        else:
            return render_template(
                "login_central.html", error="Usuário ou senha inválidos"
            )
    return render_template("login_central.html")


@app.route("/central")
def central():
    return render_template("central.html")


# ============================
# API — ALERTAS / SIRENE
# ============================

@app.route("/api/alert", methods=["POST"])
def api_alert():
    """Recebe alerta do professor e grava na lista."""
    global alertas

    data = request.get_json(force=True)
    teacher = data.get("teacher", "").strip()
    room = data.get("room", "").strip()
    description = data.get("description", "").strip()

    alerta = {
        "teacher": teacher,
        "room": room,
        "description": description,
        "ts": agora_brasilia().strftime("%d/%m/%Y %H:%M:%S"),
        "resolved": False,
    }
    # Insere no topo da lista
    alertas.insert(0, alerta)

    return jsonify({"status": "ok"})


@app.route("/api/status")
def api_status():
    """Status atual da central (lista de alertas + estado da sirene)."""
    return jsonify(
        {
            "alerts": alertas,
            "siren": siren_on,
            "muted": False,  # mantido para compatibilidade
        }
    )


@app.route("/api/siren", methods=["POST"])
def api_siren():
    """Liga/Desliga a sirene a partir da central."""
    global siren_on
    data = request.get_json(force=True)
    action = data.get("action")

    if action == "on":
        siren_on = True
    elif action == "off":
        siren_on = False

    return jsonify({"siren": siren_on})


@app.route("/api/resolve", methods=["POST"])
def resolve():
    """Marca o primeiro alerta ativo como resolvido."""
    global alertas
    for a in alertas:
        if not a["resolved"]:
            a["resolved"] = True
            break
    return jsonify({"status": "resolved"})


@app.route("/api/clear", methods=["POST"])
def clear():
    """Limpa todos os alertas."""
    global alertas
    alertas = []
    return jsonify({"status": "cleared"})


# ============================
# RELATÓRIO PDF (COM LOGO)
# ============================

@app.route("/report.pdf")
def report_pdf():
    """Gera o relatório em PDF com logo, dados da escola e lista de alertas."""
    global alertas, dados_escola

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)

    # Caminho da logo
    logo_path = os.path.join(app.root_path, "static", "logo_prof_safe24.png")

    # LOGO no topo, se existir
    if os.path.exists(logo_path):
        # x, y, largura, altura
        pdf.drawImage(logo_path, 50, 750, width=120, height=80, mask="auto")

    # Título
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(200, 800, "RELATÓRIO PROF-SAFE 24")

    # Cabeçalho com dados
    pdf.setFont("Helvetica", 12)
    y = 770
    data_hora = agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
    pdf.drawString(200, y, f"Data/Hora: {data_hora}")
    y -= 20
    pdf.drawString(50, y, f"Escola: {dados_escola['nome']}")
    y -= 20
    pdf.drawString(50, y, f"Endereço: {dados_escola['endereco']}")
    y -= 20
    pdf.drawString(50, y, f"Telefone: {dados_escola['telefone']}")
    y -= 20
    pdf.drawString(50, y, f"E-mail: {dados_escola['email']}")
    y -= 20
    pdf.drawString(50, y, f"Responsável: {dados_escola['responsavel']}")
    y -= 30

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Alertas Registrados:")
    y -= 25
    pdf.setFont("Helvetica", 12)

    if not alertas:
        pdf.drawString(50, y, "Nenhum alerta registrado até o momento.")
    else:
        for a in alertas:
            linha = (
                f"- {a['ts']} | {a['teacher']} | {a['room']} | "
                f"{a['description']} ({'Resolvido' if a['resolved'] else 'Ativo'})"
            )
            pdf.drawString(50, y, linha)
            y -= 18
            if y < 50:
                pdf.showPage()
                y = 800
                pdf.setFont("Helvetica", 12)

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="relatorio_prof_safe24.pdf",
    )


# ============================
# EXECUTAR LOCAL
# ============================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
