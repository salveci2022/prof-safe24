async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  return res.json();
}

async function initProfessor() {
  const btn = document.getElementById("btn-alert");
  const statusEl = document.getElementById("status");
  btn.addEventListener("click", async () => {
    const teacher = document.getElementById("teacher").value.trim();
    const room = document.getElementById("room").value.trim();
    statusEl.textContent = "Enviando alerta...";
    try {
      const data = await api("/api/alert", {
        method: "POST",
        body: JSON.stringify({ teacher, room })
      });
      if (data.ok) {
        statusEl.textContent = "✅ Alerta enviado com sucesso!";
      } else {
        statusEl.textContent = "⚠️ Não foi possível enviar o alerta.";
      }
    } catch (e) {
      statusEl.textContent = "Erro de comunicação com o servidor.";
    }
  });
}

function renderAlerts(alerts) {
  const container = document.getElementById("alerts");
  container.innerHTML = "";
  if (!alerts.length) {
    container.innerHTML = "<p>Nenhum alerta ativo.</p>";
    return;
  }
  for (const a of alerts) {
    const div = document.createElement("div");
    div.className = "alert-card" + (a.resolved ? " resolved" : "");
    const left = document.createElement("div");
    left.innerHTML = `<strong>${a.teacher}</strong><br/><small>${a.room} — ${a.ts}</small>`;
    const right = document.createElement("div");
    const badge = document.createElement("span");
    badge.className = "badge " + (a.resolved ? "resolved" : "active");
    badge.textContent = a.resolved ? "Resolvido" : "Ativo";
    right.appendChild(badge);
    div.appendChild(left);
    div.appendChild(right);
    container.appendChild(div);
  }
}

async function pollCentral() {
  const statusEl = document.getElementById("status");
  async function tick() {
    try {
      const data = await api("/api/status");
      renderAlerts(data.alerts || []);
      statusEl.textContent = data.siren ? "🔴 Sirene ativa" : "🟢 Sirene desligada";
    } catch (e) {
      statusEl.textContent = "Erro ao atualizar status.";
    }
    setTimeout(tick, 3000);
  }
  tick();
}

async function initCentral() {
  pollCentral();
  document.getElementById("btn-resolve").onclick = () =>
    api("/api/resolve", { method: "POST", body: JSON.stringify({}) });
  document.getElementById("btn-clear").onclick = () =>
    api("/api/clear", { method: "POST", body: JSON.stringify({}) });
  document.getElementById("btn-siren-on").onclick = () =>
    api("/api/siren", { method: "POST", body: JSON.stringify({ action: "on" }) });
  document.getElementById("btn-siren-off").onclick = () =>
    api("/api/siren", { method: "POST", body: JSON.stringify({ action: "off" }) });
}

document.addEventListener("DOMContentLoaded", () => {
  const role = document.body.dataset.role;
  if (role === "professor") initProfessor();
  if (role === "central") initCentral();
});
