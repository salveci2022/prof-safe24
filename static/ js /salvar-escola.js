// salvar-escola.js
document.getElementById("formEscola").addEventListener("submit", async function (e) {
    e.preventDefault();

    const data = {
        nome: document.getElementById("nome").value,
        endereco: document.getElementById("endereco").value,
        telefone: document.getElementById("telefone").value,
        email: document.getElementById("email").value,
        responsavel: document.getElementById("responsavel").value
    };

    const resposta = await fetch("/salvar_escola", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });

    if (resposta.ok) {
        alert("Dados da escola salvos com sucesso!");
    } else {
        alert("Erro ao salvar os dados.");
    }
});
