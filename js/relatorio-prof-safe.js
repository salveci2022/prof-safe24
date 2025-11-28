// relatorio-prof-safe.js - CÓDIGO ATUALIZADO E PRONTO

// ==================== CONFIGURAÇÃO DA ESCOLA ====================
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

--- Continua...
