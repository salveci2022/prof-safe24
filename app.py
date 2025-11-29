from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from reportlab.pdfgen import canvas
from datetime import datetime
import io
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ============================
# CONFIGURAÇÃO INICIAL
# ============================

CENTRAL_USER = "admin"
CENTRAL_PASS = "1234"

dados_escola = {
    "nome": "",
    "endereco": "",
    "telefone": "",
    "email": "",
    "responsavel": ""
}

alertas = []
siren_on = False


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
        dados_escola["nome"] = request.form.get("nome")
        dados_escola["endereco"] = request.form.get("endereco")
        dados_escola["telefone"] = request.form.get("telefone")
        dados_escola["email"] = request.form.get("email")
        dados_escola["responsavel"] = request.form.get("responsavel")
        return redirect("/admin")
    return render_template("admin_school.html", escola=dados_escola)


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    if request.method == "POST":
        user = request.form.get("usuario")
        pw = request.form.get("senha")
        if user == CENTRAL_USER and pw == CENTRAL_PASS:
            return redirect("/central")
        else:
            return render_template("login_central.html", error="Usuário ou senha inválidos")
    return render_template("login_central.html")


@app.route("/central")
def central():
    return render_template("central.html")


# ============================
# API — ALERTAS
# ============================

@app.route("/api/alert", methods=["POST"])
def api_alert():
    global alertas
    data = request.json
    alerta = {
        "teacher": data["teacher"],
        "room": data["room"],
        "description": data["description"],
        "ts": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "resolved": False
    }
    alertas.insert(0, alerta)
    return jsonify({"status": "ok"})


@app.route("/api/status")
def api_status():
    return jsonify({
        "alerts": alertas,
        "siren": siren_on,
        "muted": False
    })


@app.route("/api/siren", methods=["POST"])
def api_siren():
    global siren_on
    action = request.json.get("action")
    siren_on = (action == "on")
    return jsonify({"siren": siren_on})


@app.route("/api/resolve", methods=["POST"])
def resolve():
    global alertas
    for a in alertas:
        if not a["resolved"]:
            a["resolved"] = True
            break
    return jsonify({"status": "resolved"})


@app.route("/api/clear", methods=["POST"])
def clear():
    global alertas
    alertas = []
    return jsonify({"status": "cleared"})


# ============================
# GERAR RELATÓRIO PDF
# ============================

@app.route("/report.pdf")
def report_pdf():
    global alertas, dados_escola

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 800, "RELATÓRIO PROF-SAFE 24")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    pdf.drawString(50, 750, f"Escola: {dados_escola['nome']}")
    pdf.drawString(50, 730, f"Endereço: {dados_escola['endereco']}")
    pdf.drawString(50, 710, f"Telefone: {dados_escola['telefone']}")
    pdf.drawString(50, 690, f"Responsável: {dados_escola['responsavel']}")

    y = 650
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Alertas Registrados:")
    y -= 30

    pdf.setFont("Helvetica", 12)
    for a in alertas:
        pdf.drawString(50, y, f"- {a['ts']} | {a['teacher']} | {a['room']} | {a['description']} ({'Resolvido' if a['resolved'] else 'Ativo'})")
        y -= 20
        if y < 50:
            pdf.showPage()
            y = 800

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="relatorio.pdf")


# ============================
# EXECUTAR
# ============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
