// relatorio-prof-safe.js - CÓDIGO ATUALIZADO E PRONTO

// ==================== CONFIGURAÇÃO DA ESCOLA ====================
// ⚠️ EDITAR ESTES DADOS COM AS INFORMAÇÕES DA SUA ESCOLA ⚠️
const configEscola = {
    nome: "ESCOLA ESTADUAL PROFESSOR JOSÉ DA SILVA",
    endereco: "Rua das Flores, 123 - Centro - São Paulo/SP",
    telefone: "(11) 9999-8888",
    email: "contato@escolajosesilva.edu.br",
    responsavel: "Maria Oliveira - Diretora"
};

// ==================== FUNÇÃO HORA CORRETA ====================
function getDataHoraBrasil() {
    const agora = new Date();
    return agora.toLocaleString('pt-BR', {
        timeZone: 'America/Sao_Paulo',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

// ==================== GERAR RELATÓRIO COMPLETO ====================
function gerarRelatorioAtualizado() {
    const dataHora = getDataHoraBrasil();
    
    return `
# PROF-SAFE 24 - RELATÓRIO DE SEGURANÇA

**Instituição:** ${configEscola.nome}
**Endereço:** ${configEscola.endereco}
**Contato:** ${configEscola.telefone} | ${configEscola.email}
**Responsável:** ${configEscola.responsavel}
**Data/Hora:** ${dataHora}

---

## STATUS DO SISTEMA

- ✅ Sistema operando normalmente
- 📊 Nenhum alerta registrado
- 🔒 Todos os recursos disponíveis
- 📍 Monitoramento ativo

## PRÓXIMAS AÇÕES

- Manutenção preventiva programada
- Atualização automática de relatórios
- Backup diário dos dados

---

*Relatório gerado automaticamente pelo PROF-SAFE 24*
*Sistema de proteção escolar - ${dataHora}*
    `.trim();
}

// ==================== ATUALIZAR NA TELA ====================
function atualizarRelatorio() {
    const relatorio = gerarRelatorioAtualizado();
    
    // Atualiza na página web
    const elemento = document.getElementById('relatorio-container');
    if (elemento) {
        elemento.innerHTML = relatorio;
    }
    
    // Atualiza o título com hora atual
    document.title = `PROF-SAFE 24 - ${getDataHoraBrasil()}`;
    
    console.log("✅ Relatório atualizado com sucesso!");
    console.log(relatorio);
}

// ==================== INICIAR SISTEMA ====================
// Executar quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 PROF-SAFE 24 - Sistema de relatórios iniciado");
    atualizarRelatorio();
    
    // Atualizar a cada 30 segundos (opcional)
    setInterval(atualizarRelatorio, 30000);
});

// ==================== TESTE RÁPIDO ====================
function testeRapido() {
    const relatorio = gerarRelatorioAtualizado();
    console.log("📄 RELATÓRIO DE TESTE:");
    console.log(relatorio);
    alert("Relatório gerado! Verifique o console.");
    return relatorio;
}

// ==================== INSTRUÇÕES ====================
console.log(`
🎯 INSTRUÇÕES PROF-SAFE 24:

1. EDITAR dados da escola nas primeiras linhas
2. CHAME atualizarRelatorio() para atualizar na tela
3. CHAME testeRapido() para ver no console
4. Sistema atualiza automaticamente a cada 30s

📋 DADOS ATUAIS:
Escola: ${configEscola.nome}
Última atualização: ${getDataHoraBrasil()}
`);
