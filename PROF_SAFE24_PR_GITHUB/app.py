
import os, uuid, threading, datetime
from flask import Flask, jsonify, request, render_template, send_file
from dotenv import load_dotenv
import requests

load_dotenv()
app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","").strip()
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID","").strip()
TWILIO_SID   = os.getenv("TWILIO_SID","").strip()
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN","").strip()
TWILIO_FROM  = os.getenv("TWILIO_FROM","").strip()
TWILIO_TO    = os.getenv("TWILIO_TO","").strip()

ALERTS = []
SIREN_ACTIVE = False
MUTED = False
LOCK = threading.Lock()

def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_telegram(text: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False, "Telegram desativado"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        return (r.status_code==200), f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def send_sms(text: str):
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and TWILIO_TO):
        return False, "SMS desativado"
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        r = requests.post(url, data={"From":TWILIO_FROM,"To":TWILIO_TO,"Body":text}, auth=(TWILIO_SID,TWILIO_TOKEN), timeout=10)
        return (r.status_code in (200,201)), f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def notify_all_channels(msg: str):
    threading.Thread(target=lambda: send_telegram(msg), daemon=True).start()
    threading.Thread(target=lambda: send_sms(msg), daemon=True).start()

@app.get("/")
def home():
    return render_template("home.html")

@app.get("/professor")
def professor():
    return render_template("professor.html")

@app.get("/central")
def central():
    return render_template("central.html")

@app.get("/admin")
def admin():
    return render_template("admin.html")

@app.get("/api/status")
def api_status():
    with LOCK:
        return jsonify({"siren": SIREN_ACTIVE, "muted": MUTED, "alerts": ALERTS})

@app.post("/api/alert")
def api_alert():
    data = request.get_json(silent=True) or {}
    teacher = (data.get("teacher") or "Professor(a)").strip()
    room = (data.get("room") or "Sala ?").strip()
    alert = {"id": str(uuid.uuid4()), "teacher": teacher, "room": room, "ts": now_iso(), "resolved": False}
    with LOCK:
        ALERTS.insert(0, alert)
        global SIREN_ACTIVE
        SIREN_ACTIVE = True
    notify_all_channels(f"🚨 ALERTA: {teacher} — {room} — {alert['ts']}")
    return jsonify({"ok": True, "alert": alert})

@app.post("/api/resolve")
def api_resolve():
    data = request.get_json(silent=True) or {}
    alert_id = data.get("id")
    updated = False
    with LOCK:
        if alert_id:
            for a in ALERTS:
                if a["id"] == alert_id:
                    a["resolved"] = True
                    updated = True
                    break
        else:
            for a in ALERTS:
                if not a["resolved"]:
                    a["resolved"] = True
                    updated = True
                    break
        global SIREN_ACTIVE
        SIREN_ACTIVE = any(not x["resolved"] for x in ALERTS)
    return jsonify({"ok": True, "updated": updated, "siren": SIREN_ACTIVE})

@app.post("/api/clear")
def api_clear():
    with LOCK:
        ALERTS.clear()
        global SIREN_ACTIVE
        SIREN_ACTIVE = False
    return jsonify({"ok": True})

@app.post("/api/siren")
def api_siren():
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").lower()
    global SIREN_ACTIVE, MUTED
    with LOCK:
        if action == "on": SIREN_ACTIVE = True
        elif action == "off": SIREN_ACTIVE = False
        elif action == "mute": MUTED = True
        elif action == "unmute": MUTED = False
    return jsonify({"ok": True, "siren": SIREN_ACTIVE, "muted": MUTED})

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER

def build_pdf(buffer, alerts, generated_by="PROF-SAFE 24"):
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    title = styles['Title']; title.fontName='Helvetica-Bold'; title.fontSize=24; title.leading=28; title.alignment=TA_CENTER
    normal = styles['Normal']; normal.fontName='Helvetica'; normal.fontSize=11; normal.leading=14

    elements = []
    elements.append(Paragraph("PROF-SAFE 24 — Relatório de Ocorrências", title))
    elements.append(Spacer(1, 6*mm))
    now = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    header_text = f"Gerado em: {now} — Total de alertas: {len(alerts)} — Origem: {generated_by}"
    elements.append(Paragraph(header_text, normal))
    elements.append(Spacer(1, 4*mm))

    if alerts:
        data = [["#","Professor(a)","Sala","Data/Hora","Status"]]
        for i,a in enumerate(alerts, start=1):
            status = "Resolvido" if a.get('resolved') else "Ativo"
            data.append([str(i), a.get('teacher','—'), a.get('room','—'), a.get('ts','—'), status])
        tbl = Table(data, colWidths=[12*mm, 55*mm, 25*mm, 50*mm, 25*mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0), colors.Color(0.07,0.09,0.12)),
            ('TEXTCOLOR',(0,0),(-1,0), colors.whitesmoke),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),12),
            ('ALIGN',(0,0),(-1,0),'CENTER'),
            ('GRID',(0,0),(-1,-1),0.25, colors.Color(0.65,0.72,0.80)),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.Color(0.95,0.97,1), colors.white]),
            ('FONTSIZE',(0,1),(-1,-1),10),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        elements.append(tbl)
    else:
        elements.append(Paragraph("Nenhum alerta registrado no período.", normal))

    doc.build(elements)

@app.get("/report.pdf")
def report_pdf():
    from io import BytesIO
    buf = BytesIO()
    with LOCK:
        current = list(ALERTS)
    build_pdf(buf, current, "Painel Central")
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="relatorio_prof_safe24.pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=True)
