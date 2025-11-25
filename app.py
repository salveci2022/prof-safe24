import os
import datetime
from io import BytesIO

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    send_file
)
from dotenv import load_dotenv
from reportlab.pdfgen import canvas

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "mude_esta_chave")
CENTRAL_USER = os.getenv("CENTRAL_USER", "central")
CENTRAL_PASS = os.getenv("CENTRAL_PASS", "1234")

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

@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    error = None
    if request.method == "POST":
        usuario = request.form.get("usuario","").strip()
        senha = request.form.get("senha","").strip()
        if usuario == CENTRAL_USER and senha == CENTRAL_PASS:
            session["central_logged"] = True
            return redirect(url_for("central"))
        else:
            error = "Usuário ou senha inválidos."
    return render_template("login_central.html", error=error)

@app.route("/central")
def central():
    if not session.get("central_logged"):
        return redirect(url_for("login_central"))
    return render_template("central.html")

@app.route("/logout_central")
def logout_central():
    session.pop("central_logged", None)
    return redirect(url_for("home"))

@app.route("/api/alert", methods=["POST"])
def api_alert():
    global alerts, siren_on, muted
    data = request.get_json(silent=True) or {}
    teacher = (data.get("teacher") or "").strip()
    room = (data.get("room") or "").strip()
    description = (data.get("description") or "").strip()
    if not room or not description:
        return jsonify({"ok": False}), 400
    ts = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    alerts.insert(0,{
        "teacher": teacher,
        "room": room,
        "description": description,
        "ts": ts,
        "resolved": False
    })
    siren_on = True
    muted = False
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
        siren_on = True; muted = False
    elif action == "off":
        siren_on = False; muted = False
    elif action == "mute":
        siren_on = True; muted = True
    else:
        return jsonify({"ok": False}), 400
    return jsonify({"ok": True})

@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    global alerts
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

@app.route("/report.pdf")
def report_pdf():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle("Relatório")
    pdf.drawString(40,800,"PROF-SAFE 24 - Relatório")
    y = 760
    for idx,a in enumerate(alerts,start=1):
        if y<80:
            pdf.showPage(); y=800
        pdf.drawString(40,y,f"{idx}. Professor: {a['teacher']} Sala: {a['room']}"); y-=14
        pdf.drawString(40,y,f"   Data/Hora: {a['ts']} Status: {'Resolvido' if a['resolved'] else 'Ativo'}"); y-=14
        pdf.drawString(40,y,f"   Desc: {a['description']}"); y-=20
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=False, download_name="relatorio.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
