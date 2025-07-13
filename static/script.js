// Formatação de campos de período
function formatarPeriodo(input) {
    input.addEventListener('input', function() {
        let valor = this.value.replace(/\D/g, '');
        if (valor.length > 2) {
            valor = valor.substring(0, 2) + '/' + valor.substring(2, 6);
        }
        this.value = valor;
    });
}

// Aplicar formatação aos campos
document.addEventListener('DOMContentLoaded', function() {
    formatarPeriodo(document.getElementById('periodoInicial'));
    formatarPeriodo(document.getElementById('periodoFinal'));
});

// Conexão Socket.IO
const socket = io();

socket.on('connect', () => {
    console.log('Conectado ao servidor Socket.IO');
});

socket.on('encerramento_concluido', (data) => {
    console.log('Recebido evento de encerramento concluído:', data);
    alert(`Encerramento concluído para CNPJ: ${data.cnpj}`);
    location.reload();
});

socket.on('atualizacao_status', (data) => {
    console.log('Recebido atualização de status:', data);
    const row = document.querySelector(`tr[data-cnpj="${data.cnpj}"]`);
    if (row) {
        const statusCell = row.querySelector('td:nth-child(6)');
        if (statusCell) {
            statusCell.innerHTML = `
                <div class="d-flex flex-column">
                    <span class="badge bg-warning">${data.status}</span>
                    <div class="progress">
                        <div class="progress-bar" role="progressbar" style="width: ${data.progresso}%" 
                             aria-valuenow="${data.progresso}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                </div>
            `;
        }
    }
});

function abrirModal(element) {
    const cnpj = element.getAttribute('data-cnpj');
    document.getElementById('cnpjEmpresa').value = cnpj;
    
    // Limpar campos
    document.getElementById('periodoInicial').value = '';
    document.getElementById('periodoFinal').value = '';
    // document.getElementById('bot_path').checked = false;

                
    // Remover validações anteriores
    document.getElementById('encerramentoForm').classList.remove('was-validated');
    
    new bootstrap.Modal(document.getElementById('encerramentoModal')).show();
}

// Event listener para atualizar bot_path com base no checkbox selecionado
document.getElementById('servicosTomados').addEventListener('change', function() {
    if (this.checked) {
        document.getElementById('bot_path').value = 'bots/bot.py';
    }
});

document.getElementById('servicosPrestados').addEventListener('change', function() {
    if (this.checked) {
        document.getElementById('bot_path').value = 'bots/bot2.py';
    }
});

document.getElementById('encerramentoForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Validação básica
    const form = this;
    if (!form.checkValidity()) {
        form.classList.add('was-validated');
        return;
    }

    const formData = new FormData(form);
    const cnpj = formData.get('cnpj');
    let periodo_inicial = formData.get('periodo_inicial').replace('/', '');
    let periodo_final = formData.get('periodo_final').replace('/', '');
    const bot_path = formData.get('bot_path');

    // Validação de formato
    if (!/^\d{6}$/.test(periodo_inicial) || !/^\d{6}$/.test(periodo_final)) {
        alert('Formato de período inválido. Use MM/AAAA');
        return;
    }

    // Mostrar spinner
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.querySelector('.btn-text').style.display = 'none';
    submitBtn.querySelector('.btn-spinner').style.display = 'inline-block';

    // Log para depuração
    console.log('Dados enviados para o backend:', {
        cnpj,
        periodo_inicial,
        periodo_final,
        bot_path
    });

    // Envia os dados via POST
    fetch('/encerrar', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            cnpj: cnpj,
            periodo_inicial: periodo_inicial,
            periodo_final: periodo_final,
            bot_path: bot_path
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Resposta do backend:', data);
        if (data.message) {
            alert('Processo iniciado com sucesso!');
            bootstrap.Modal.getInstance(document.getElementById('encerramentoModal')).hide();
            
            // Atualizar a linha da tabela
            const row = document.querySelector(`tr[data-cnpj="${cnpj}"]`);
            if (row) {
                const statusCell = row.querySelector('td:nth-child(6)');
                if (statusCell) {
                    statusCell.innerHTML = `
                        <div class="d-flex flex-column">
                            <span class="badge bg-warning">em_processo</span>
                            <div class="progress">
                                <div class="progress-bar" role="progressbar" style="width: 0%" 
                                    aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                        </div>
                    `;
                }
            }
        }
    })
    .catch(async error => {
        let msg = error.message;
        try {
            const resp = await error.response.json();
            if (resp.error) msg += ' - ' + resp.error;
        } catch {}
        alert('Erro ao processar: ' + msg);
    })

    .finally(() => {
        // Esconder spinner
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-text').style.display = 'inline';
        submitBtn.querySelector('.btn-spinner').style.display = 'none';
    });
});

// Seleção de todos os checkboxes
document.getElementById('selectAll').addEventListener('change', function() {
    const checkboxes = document.querySelectorAll('tbody .form-check-input');
    for (let checkbox of checkboxes) {
        checkbox.checked = this.checked;
    }
});