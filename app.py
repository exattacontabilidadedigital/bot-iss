from flask import Flask, render_template_string, request, jsonify
import sqlite3
import re

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Exatta Contabilidade Digital</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --exatta-dark-blue: #061440;
            --exatta-red: #e73030;
        }
        body { background: #f8f9fa; margin: 0; padding: 0; }
        .navbar-exatta {
            background-color: var(--exatta-dark-blue);
            padding: 15px 30px;
        }
        .nav-link {
            color: white !important;
            margin-right: 20px;
            font-weight: 500;
        }
        .nav-link.active {
            color: var(--exatta-red) !important;
        }
        .container-fluid { padding: 30px; }
        h1 { 
            margin-bottom: 30px; 
            font-size: 28px;
            font-weight: 500;
            color: #333;
        }
        .actions-btn {
            background-color: var(--exatta-dark-blue);
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 5px;
        }
        .filter-container {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .filter-select {
            width: 200px;
            border-radius: 5px;
            padding: 8px;
            border: 1px solid #ddd;
        }
        .table {
            border-collapse: separate;
            border-spacing: 0;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
        }
        .table th {
            background-color: #f8f9fa;
            color: #333;
            font-weight: 500;
            border-bottom: 1px solid #ddd;
        }
        .badge.bg-danger {
            background-color: #ffebee !important;
            color: #f44336 !important;
        }
        .badge.bg-success {
            background-color: #e8f5e9 !important;
            color: #4caf50 !important;
        }
        .action-icon {
            color: #888;
        }
        .logo-text {
            color: white;
            font-weight: bold;
            font-size: 24px;
        }
        .logo-text span {
            color: var(--exatta-red);
        }
    </style>
</head>
<body>
    <!-- Barra de navegação -->
    <nav class="navbar navbar-expand navbar-exatta">
        <div class="container-fluid px-4">
            <a class="navbar-brand" href="#">
                <div class="logo-text"><span>e</span>xatta</div>
                <div style="font-size: 12px; color: #ccc; margin-top: -5px;">Contabilidade Digital</div>
            </a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="#">Dashboard</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#">Emitir Nota</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="#">Fechamento</a>
                    </li>
                </ul>
            </div>
            <div>
                <a href="#" class="text-white me-3"><i class="far fa-heart"></i></a>
                <a href="#" class="text-white me-3"><i class="far fa-bell"></i></a>
                <a href="#" class="text-white me-3"><i class="far fa-question-circle"></i></a>
                <a href="#" class="text-white"><i class="fas fa-user-circle"></i></a>
            </div>
        </div>
    </nav>

    <!-- Conteúdo principal -->
    <div class="container-fluid">
        <h1>Fechamento</h1>
        
        <div class="d-flex justify-content-between mb-4">
            <button class="actions-btn">
                <i class="fas fa-pencil-alt me-2"></i> Ações
            </button>
            
            <form method="get" id="filtros-form">
                <div class="filter-container">
                    <div>
                        <select class="form-select filter-select" name="empresa" onchange="this.form.submit()">
                            <option value="">Todas</option>
                            {% for empresa_nome in lista_empresas %}
                            <option value="{{ empresa_nome }}" {% if request.args.get('empresa') == empresa_nome %}selected{% endif %}>{{ empresa_nome }}</option>
                            {% endfor %}
                        </select>
                    </div>

                    <div>
                        <select class="form-select filter-select" name="omisso" onchange="this.form.submit()">
                            <option value="">Omissão</option>
                            <option value="Sim" {% if request.args.get('omisso')=='Sim' %}selected{% endif %}>Sim</option>
                            <option value="Não" {% if request.args.get('omisso')=='Não' %}selected{% endif %}>Não</option>
                        </select>
                    </div>

                    <div>
                        <select class="form-select filter-select" name="debito" onchange="this.form.submit()">
                            <option value="">Débito</option>
                            <option value="Sim" {% if request.args.get('debito')=='Sim' %}selected{% endif %}>Sim</option>
                            <option value="Não" {% if request.args.get('debito')=='Não' %}selected{% endif %}>Não</option>
                        </select>
                    </div>

                    <div>
                        <button type="button" class="btn btn-light border"><i class="far fa-calendar-alt"></i></button>
                    </div>
                </div>
            </form>

        </div>
        
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th style="width: 50px;">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="selectAll">
                                <label class="form-check-label" for="selectAll">Selecionar</label>
                            </div>
                        </th>
                        <th>Empresa</th>
                        <th>CNPJ</th>
                        <th>Débito</th>
                        <th>Omissão</th>
                        <th style="width: 80px;">Ação</th>
                    </tr>
                </thead>
                <tbody>
                {% for cnpj, nome, omisso, debito in empresas %}
                <tr>
                    <td>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox">
                        </div>
                    </td>
                    <td>{{ nome }}</td>
                    <td>{{ cnpj }}</td>
                    <td>
                        {% if debito == 'Sim' %}
                            <span class="badge bg-danger">sim</span>
                        {% else %}
                            <span class="badge bg-success">não</span>
                        {% endif %}
                    </td>
                    <td>
                        {% if omisso == 'Sim' %}
                            <span class="badge bg-danger">sim</span>
                        {% else %}
                            <span class="badge bg-success">não</span>
                        {% endif %}
                    </td>
                    <td class="text-center">
                        <a href="#" class="action-icon" onclick="abrirModal('{{ cnpj }}')"><i class="fas fa-pencil-alt"></i></a>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="6" class="text-center text-muted">Nenhum registro encontrado.</td>
                </tr>
                {% endfor %}
            </tbody>
            <!-- Modal -->
            <div class="modal fade" id="encerramentoModal" tabindex="-1" aria-labelledby="encerramentoModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="encerramentoModalLabel">Encerrar Movimento</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
                </div>
                <div class="modal-body">
                    <form id="encerramentoForm">
                    <input type="hidden" id="cnpjEmpresa" name="cnpj">
                    <div class="mb-3">
                        <label for="periodoInicial" class="form-label">Período Inicial (mm/aaaa)</label>
                        <input type="text" class="form-control" id="periodoInicial" name="periodo_inicial" required>
                    </div>
                    <div class="mb-3">
                        <label for="periodoFinal" class="form-label">Período Final (mm/aaaa)</label>
                        <input type="text" class="form-control" id="periodoFinal" name="periodo_final" required>
                    </div>
                    <button type="submit" class="btn btn-primary">Encerrar Movimento</button>
                    </form>
                </div>
                </div>
            </div>
            </div>
            </table>
        </div>
    </div>

    <div class="container-fluid mt-5 pt-5">
        <div class="text-muted small text-end">Made with Visily</div>
    </div>

    <script>
    document.getElementById('selectAll').addEventListener('change', function() {
        var checkboxes = document.querySelectorAll('tbody .form-check-input');
        for (var checkbox of checkboxes) {
            checkbox.checked = this.checked;
        }
    });

    function abrirModal(cnpj) {
        document.getElementById('cnpjEmpresa').value = cnpj;
        var modal = new bootstrap.Modal(document.getElementById('encerramentoModal'));
        modal.show();
    }

    document.getElementById('encerramentoForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        
        fetch('/encerrar', {
            method: 'POST',
            body: JSON.stringify({
                cnpj: formData.get('cnpj'),
                periodo_inicial: formData.get('periodo_inicial'),
                periodo_final: formData.get('periodo_final')
            }),
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            location.reload();  // Para recarregar a página depois de encerrar o movimento
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('Erro ao encerrar o movimento.');
        });


    });
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>

</body>
</html>
"""
def get_db_connection():
    conn = sqlite3.connect('empresas.db')
    conn.row_factory = sqlite3.Row
    return conn

def criar_tabela_empresas():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT,
            nome TEXT,
            omisso TEXT,
            debito TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET'])
def index():
    conn = get_db_connection()

    empresa = request.args.get('empresa')
    omisso = request.args.get('omisso')
    debito = request.args.get('debito')

    query = "SELECT cnpj, nome, omisso, debito FROM empresas WHERE 1=1"
    params = []

    if empresa:
        query += " AND nome = ?"
        params.append(empresa)
    if omisso:
        query += " AND omisso = ?"
        params.append(omisso)
    if debito:
        query += " AND debito = ?"
        params.append(debito)

    empresas = conn.execute(query, params).fetchall()
    lista_empresas = conn.execute("SELECT DISTINCT nome FROM empresas").fetchall()

    conn.close()

    return render_template_string(
        HTML,
        empresas=empresas,
        lista_empresas=[e['nome'] for e in lista_empresas],
        request=request
    )

@app.route('/encerrar', methods=['POST'])
def encerrar_movimento():
    data = request.get_json()
    cnpj = data.get('cnpj')
    periodo_inicial = data.get('periodo_inicial')
    periodo_final = data.get('periodo_final')

    # Aqui você pode fazer algo como salvar o encerramento no banco.
    print(f"Movimento encerrado para {cnpj}: {periodo_inicial} até {periodo_final}")

    return jsonify({'message': f'Movimento encerrado para o CNPJ {cnpj} de {periodo_inicial} até {periodo_final}.'})

if __name__ == '__main__':
    criar_tabela_empresas()
    app.run(debug=True)

