from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from datetime import datetime
from io import BytesIO
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "spynet-secret-key")

# =====================================================================
# 🔥 DADOS DA ESCOLA - PREMIUM (Sem alterar nada do sistema atual)
# =====================================================================

SCHOOL_NAME = os.environ.get("SCHOOL_NAME", "Escola não configurada")
SCHOOL_ADDRESS = os.environ.get("SCHOOL_ADDRESS", "Endereço não configurado")
SCHOOL_PHONE = os.environ.get("SCHOOL_PHONE", "Telefone não configurado")
SCHOOL_DIRECTOR = os.environ.get("SCHOOL_DIRECTOR", "Diretor não configurado")

# =====================================================================
# 🔐 PROTEÇÃO ANTI-CÓPIA (não interfere no resto do sistema)
# =====================================================================

LICENSE_KEY = os.environ.get("LICENSE_KEY", "NONE")
VALID_LICENSE = os.environ.get("VALID_LICENSE", "NONE")

@app.before_request
def block_unauthorized():
    if LICENSE_KEY != VALID_LICENSE:
        return """
        <h1 style='color:red;'>SISTEMA NÃO AUTORIZADO</h1>
        <p>Entre em contato com o administrador SPYNET.</p>
        """, 403

# =====================================================================
# LOGIN / ADMIN
# =====================================================================

ADMIN_USER = os.environ.get("ADMIN_USER", "central")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "1234")

alerts = []
siren_on = False
siren_muted = False

@app.route("/")
def home():
    return render_template("home.html",
        SCHOOL_NAME=SCHOOL_NAME,
        SCHOOL_ADDRESS=SCHOOL_ADDRESS
    )

@app.route("/professor")
def professor():
    return render_template("professor.html",
        SCHOOL_NAME=SCHOOL_NAME,
        SCHOOL_ADDRESS=SCHOOL_ADDRESS
    )

@app.route("/login_central", methods=["GET","POST"])
def login_central():
    error=None
    if request.method=="POST":
        u=request.form.get("usuario","").strip()
        p=request.form.get("senha","").strip()
        if u==ADMIN_USER and p==ADMIN_PASS:
            session["central_logged"]=True
            return redirect(url_for("central"))
        else:
            error="Usuário ou senha inválidos."
    return render_template("login_central.html", error=error)

@app.route("/central")
def central():
    if not session.get("central_logged"):
        return redirect(url_for("login_central"))
    return render_template("central.html",
        SCHOOL_NAME=SCHOOL_NAME,
        SCHOOL_ADDRESS=SCHOOL_ADDRESS,
        SCHOOL_PHONE=SCHOOL_PHONE,
        SCHOOL_DIRECTOR=SCHOOL_DIRECTOR
    )

@app.route("/logout_central")
def logout_central():
    session.pop("central_logged",None)
    return redirect(url_for("home"))

@app.route("/admin")
def admin():
    return render_template("admin.html",
        SCHOOL_NAME=SCHOOL_NAME,
        SCHOOL_ADDRESS=SCHOOL_ADDRESS,
        SCHOOL_PHONE=SCHOOL_PHONE,
        SCHOOL_DIRECTOR=SCHOOL_DIRECTOR
    )

@app.route("/painel_publico")
def painel_publico():
    return render_template("painel_publico.html",
        SCHOOL_NAME=SCHOOL_NAME
    )

# =====================================================================
# API — Não mexi em NADA Aqui
# =====================================================================

@app.route("/api/alert", methods=["POST"])
def api_alert():
    global alerts, siren_on
    data=request.get_json() or {}
    teacher=data.get("teacher","").strip() or "Professor(a)"
    room=data.get("room","").strip()
    desc=data.get("description","").strip()
    if not room or not desc:
        return jsonify({"ok":False,"message":"Sala e descrição são obrigatórias."}),400
    alert={
        "teacher":teacher,
        "room":room,
        "description":desc,
        "ts":datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "resolved":False
    }
    alerts.insert(0,alert)
    siren_on=True
    return jsonify({"ok":True})

@app.route("/api/status")
def api_status():
    return jsonify({"ok":True,"alerts":alerts,"siren":siren_on,"muted":siren_muted})

@app.route("/api/siren", methods=["POST"])
def api_siren():
    global siren_on, siren_muted
    data=request.get_json() or {}
    action=data.get("action","").lower()
    if action in ("start","on"):
        siren_on=True
        siren_muted=False
    elif action in ("stop","off"):
        siren_on=False
    elif action=="mute":
        siren_muted=True
    elif action=="unmute":
        siren_muted=False
    return jsonify({"ok":True,"siren":siren_on,"muted":siren_muted})

@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    global alerts, siren_on
    for a in alerts:
        if not a.get("resolved"):
            a["resolved"]=True
            break
    if not any(not a.get("resolved") for a in alerts):
        siren_on=False
    return jsonify({"ok":True})

@app.route("/api/clear", methods=["POST"])
def api_clear():
    global alerts, siren_on
    alerts=[]
    siren_on=False
    return jsonify({"ok":True})

# =====================================================================
# PDF — Aqui também mantenho tudo igual, só adiciono dados da escola
# =====================================================================

@app.route("/report.pdf")
def report_pdf():
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "SPYNET - Relatório de Ocorrências")
    y -= 25

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Escola: {SCHOOL_NAME}")
    y -= 14
    c.drawString(50, y, f"Diretor(a): {SCHOOL_DIRECTOR}")
    y -= 14
    c.drawString(50, y, f"Telefone: {SCHOOL_PHONE}")
    y -= 14
    c.drawString(50, y, f"Endereço: {SCHOOL_ADDRESS}")
    y -= 25

    c.drawString(50, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    y -= 15
    c.drawString(50, y, "Sistema: PROF-SAFE24 - Painel de Alerta Escolar em Tempo Real")
    y -= 25

    if not alerts:
        c.drawString(50, y, "Nenhuma ocorrência registrada até o momento.")
    else:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Ocorrências:")
        y -= 20
        c.setFont("Helvetica", 10)

        for idx, a in enumerate(reversed(alerts), start=1):
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica-Bold", 11)
                c.drawString(50, y, "Ocorrências (continuação):")
                y -= 20
                c.setFont("Helvetica", 10)

            status = "Resolvido" if a.get("resolved") else "Ativo"
            linha = f"{idx}) Sala: {a.get('room','-')} | Prof.: {a.get('teacher','-')} | Status: {status}"
            c.drawString(50, y, linha[:120])
            y -= 14
            desc = f"    {a.get('ts','-')} - {a.get('description','')}"
            c.drawString(50, y, desc[:120])
            y -= 18

    c.showPage()
    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="relatorio_spynet_prof_safe24.pdf",
    )

# =====================================================================
# RUN
# =====================================================================

if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)
