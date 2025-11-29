
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from datetime import datetime
import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)

# Dados em memória (para cada instância do servidor)
alerts = []
school_data = {
    "nome": "",
    "cnpj": "",
    "endereco": "",
    "telefone": ""
}
sirene_modo = "som_visual"  # "som_visual" ou "visual"


# =======================
# ROTAS DE PÁGINA
# =======================

@app.route("/")
def index():
    # Tela inicial simples com links
    return render_template("index.html", escola=school_data)


@app.route("/professor")
def professor():
    return render_template("professor.html", escola=school_data)


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    erro = None
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()
        if usuario == "Centralfe3642620" and senha == "PS24@central":
            return redirect(url_for("central"))
        else:
            erro = "Usuário ou senha inválidos."
    return render_template("login_central.html", erro=erro)


@app.route("/central")
def central():
    return render_template("central.html", escola=school_data, sirene_modo=sirene_modo)


# =======================
# API ESCOLA
# =======================

@app.route("/api/escola", methods=["GET", "POST"])
def api_escola():
    """GET devolve dados da escola, POST atualiza."""
    global school_data
    if request.method == "POST":
        data = request.get_json(force=True)
        school_data["nome"] = data.get("nome", "").strip()
        school_data["cnpj"] = data.get("cnpj", "").strip()
        school_data["endereco"] = data.get("endereco", "").strip()
        school_data["telefone"] = data.get("telefone", "").strip()
        return jsonify({"status": "ok", "escola": school_data})
    return jsonify(school_data)


# =======================
# API ALERTAS
# =======================

@app.route("/api/alerta", methods=["POST"])
def api_alerta():
    """Recebe um alerta enviado pelo professor."""
    global alerts
    data = request.get_json(force=True)
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    alerta = {
        "datahora": agora,
        "professor": data.get("professor", "").strip() or "Não informado",
        "sala": data.get("sala", "").strip() or "Não informado",
        "tipo": data.get("tipo", "").strip() or "Outra situação",
        "urgencia": data.get("urgencia", "").strip() or "Média",
        "descricao": data.get("descricao", "").strip(),
        "status": "Ativo"
    }
    # último alerta fica no topo
    alerts.insert(0, alerta)
    return jsonify({"status": "ok", "sirene": sirene_modo})


@app.route("/api/alertas", methods=["GET"])
def api_alertas():
    return jsonify(alerts)


@app.route("/api/alertas/limpar", methods=["POST"])
def api_alertas_limpar():
    global alerts
    alerts = []
    return jsonify({"status": "ok"})


@app.route("/api/alertas/resolver_primeiro", methods=["POST"])
def api_alertas_resolver_primeiro():
    # marca o mais antigo como resolvido, se existir
    if alerts:
        alerts[-1]["status"] = "Resolvido"
    return jsonify({"status": "ok"})


# =======================
# API SIRENE
# =======================

@app.route("/api/sirene_modo", methods=["GET", "POST"])
def api_sirene_modo():
    global sirene_modo
    if request.method == "POST":
        data = request.get_json(force=True)
        modo = data.get("modo")
        if modo in ("som_visual", "visual"):
            sirene_modo = modo
    return jsonify({"modo_atual": sirene_modo})


@app.route("/sirene.mp3")
def sirene_file():
    """Serve o arquivo de áudio da sirene."""
    caminho = os.path.join(app.static_folder, "sirene.mp3")
    if not os.path.exists(caminho):
        # fallback simples se o arquivo não existir
        return ("Arquivo de sirene não encontrado. "
                "Envie o arquivo 'sirene.mp3' para a pasta static do servidor."), 404
    return send_file(caminho, mimetype="audio/mpeg")


# =======================
# RELATÓRIO PDF
# =======================

@app.route("/relatorio.pdf")
def relatorio_pdf():
    """Gera relatório PDF com histórico de ocorrências."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, altura - 50, "PROF-SAFE 24 - Relatório de Ocorrências")

    y = altura - 90
    p.setFont("Helvetica", 10)

    if school_data.get("nome"):
        p.drawString(50, y, f"Escola: {school_data['nome']}")
        y -= 14
    if school_data.get("cnpj"):
        p.drawString(50, y, f"CNPJ: {school_data['cnpj']}")
        y -= 14
    if school_data.get("endereco"):
        p.drawString(50, y, f"Endereço: {school_data['endereco']}")
        y -= 14
    if school_data.get("telefone"):
        p.drawString(50, y, f"Contato: {school_data['telefone']}")
        y -= 20

    if not alerts:
        p.drawString(50, y, "Nenhuma ocorrência registrada.")
    else:
        for alerta in alerts:
            if y < 80:
                p.showPage()
                y = altura - 50
                p.setFont("Helvetica", 10)

            texto = (
                f"Data/Hora: {alerta['datahora']} | Professor: {alerta['professor']} | "
                f"Sala: {alerta['sala']} | Urgência: {alerta['urgencia']} | "
                f"Tipo: {alerta['tipo']} | Status: {alerta['status']}"
            )
            p.drawString(50, y, texto)
            y -= 14
            if alerta["descricao"]:
                p.drawString(60, y, f"Descrição: {alerta['descricao']}")
                y -= 18

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="relatorio_prof_safe24.pdf",
    )


# =======================
# ROTA DE TESTE / SAÚDE
# =======================

@app.route("/teste")
def teste():
    return "API OK - PROF_SAFE24 rodando."


# =======================
# INÍCIO DA APLICAÇÃO – PORTA DO RENDER
# =======================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
