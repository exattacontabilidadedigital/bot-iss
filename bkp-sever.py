import os
import re
import logging
import sqlite3
import subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from functools import wraps

# Configurações iniciais
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'segredo_super_secreto')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Pool de threads para execução assíncrona
executor = ThreadPoolExecutor(max_workers=5)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('EncerramentoISS')

def validar_cnpj(cnpj):
    """Valida formato do CNPJ usando regex"""
    return re.match(r'^\d{14}$', cnpj) is not None

def validar_periodo(periodo):
    """Valida formato MMAAAA"""
    return re.match(r'^\d{6}$', periodo) is not None

def transacao_db(func):
    """Decorator para gerenciar transações de banco de dados"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = sqlite3.connect('empresas.db')
        try:
            result = func(conn, *args, **kwargs)
            conn.commit()
            return result
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erro DB: {str(e)}")
            raise
        finally:
            conn.close()
    return wrapper

@transacao_db
def atualizar_status(conn, cnpj, status, progresso='0'):
    """Atualiza status da empresa no banco de dados"""
    cursor = conn.cursor()
    
    # Verificar se as colunas existem
    cursor.execute("PRAGMA table_info(empresas)")
    colunas = [col[1] for col in cursor.fetchall()]
    
    # Se a coluna 'status' não existir, cria a coluna
    if 'status' not in colunas:
        cursor.execute("ALTER TABLE empresas ADD COLUMN status TEXT DEFAULT 'pendente'")
    
    # Se a coluna 'progresso' não existir, cria a coluna
    if 'progresso' not in colunas:
        cursor.execute("ALTER TABLE empresas ADD COLUMN progresso TEXT DEFAULT '0'")
    
    cursor.execute('''
        UPDATE empresas 
        SET status = ?, progresso = ? 
        WHERE cnpj = ?
    ''', (status, progresso, cnpj))

@app.route('/encerrar', methods=['POST'])
def iniciar_encerramento():
    try:
        dados = request.get_json()
        
        # Validação rigorosa
        if not all(k in dados for k in ('cnpj', 'periodo_inicial', 'periodo_final')):
            return jsonify({'error': 'Parâmetros ausentes'}), 400

        cnpj = re.sub(r'\D', '', dados['cnpj'])
        periodo_inicial = dados['periodo_inicial'].replace('/', '')
        periodo_final = dados['periodo_final'].replace('/', '')
        
        if not validar_cnpj(cnpj):
            return jsonify({'error': 'CNPJ inválido'}), 400
            
        if not all(validar_periodo(p) for p in (periodo_inicial, periodo_final)):
            return jsonify({'error': 'Período inválido. Use MMAAAA'}), 400

        # Atualiza status inicial
        atualizar_status(None, cnpj, 'em_processo')
        
        # Execução assíncrona do bot
        executor.submit(
            executar_bot,
            cnpj,
            periodo_inicial,
            periodo_final
        )
        
        return jsonify({
            'message': 'Processo iniciado com sucesso',
            'cnpj': cnpj,
            'status': 'em_processo'
        }), 202

    except Exception as e:
        logger.error(f"Erro geral: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

def executar_bot(cnpj, periodo_inicial, periodo_final):
    try:
        # Atualizar status para "em_processo"
        atualizar_status(cnpj, 'em_processo')

        # Caminho para o script do bot
        bot_path = os.path.join(os.path.dirname(__file__), 'bots', 'bot.py')
        
        # Executar o bot como processo separado
        result = subprocess.run(
            ['python', bot_path, cnpj, periodo_inicial, periodo_final],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Verificar resultado
        if result.returncode == 0:
            logger.info(f"Bot concluído com sucesso para CNPJ {cnpj}")
            atualizar_status(cnpj, 'concluido', '100')
            socketio.emit('encerramento_concluido', {
                'message': f'Movimento para {cnpj} encerrado com sucesso!',
                'cnpj': cnpj
            })
            return True
        else:
            logger.error(f"Erro no bot: {result.stderr}")
            atualizar_status(None, cnpj, 'erro', '0')
            socketio.emit('erro_processo', {
                'message': f'Erro ao encerrar movimento: {result.stderr}',
                'cnpj': cnpj
            })
            return False
    except Exception as e:
        logger.error(f"Erro ao executar bot: {str(e)}")
        atualizar_status(None, cnpj, 'erro', '0')
        socketio.emit('erro_processo', {
            'message': f'Erro ao executar processo: {str(e)}',
            'cnpj': cnpj
        })
        return False

@app.route('/status/<cnpj>', methods=['GET'])
def obter_status(cnpj):
    try:
        with sqlite3.connect('empresas.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status, progresso, ultima_atualizacao 
                FROM empresas 
                WHERE cnpj = ?
            ''', (cnpj,))
            resultado = cursor.fetchone()
            
            if not resultado:
                return jsonify({'error': 'CNPJ não encontrado'}), 404
                
            return jsonify({
                'cnpj': cnpj,
                'status': resultado[0],
                'progresso': resultado[1],
                'ultima_atualizacao': resultado[2]
            })
            
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    logger.info('Cliente conectado via WebSocket')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Cliente desconectado')

@socketio.on('atualizar_status')
def handle_status_update(data):
    logger.info(f"Atualização de status recebida: {data}")
    socketio.emit('atualizacao_status', data)

@app.route("/")
def index():
    try:
        # Conecta ao banco de dados
        conn = sqlite3.connect('empresas.db')
        cur = conn.cursor()
        
        # Verificar se as colunas existem
        cur.execute("PRAGMA table_info(empresas)")
        colunas = [col[1] for col in cur.fetchall()]
        
        # Consulta adaptativa
        if 'status' in colunas and 'progresso' in colunas:
            query = '''
                SELECT im, cnpj, nome, omisso, debito, status, progresso
                FROM empresas
            '''
        else:
            query = 'SELECT im, cnpj, nome, omisso, debito FROM empresas'
        
        cur.execute(query)
        resultados = cur.fetchall()
        
        # Processamento dos resultados
        empresas = []
        for row in resultados:
            empresa = {
                'im': row[0],
                'cnpj': row[1],
                'nome': row[2],
                'omisso': row[3],
                'debito': row[4]
            }
            
            if len(row) > 5:
                empresa.update({
                    'status': row[5] or 'pendente',
                    'progresso': row[6] or '0'
                })
            
            empresas.append(empresa)
        
        # Lista única de nomes para filtro
        cur.execute("SELECT DISTINCT nome FROM empresas")
        lista_empresas = [row[0] for row in cur.fetchall()]
        
        # Carregar o template HTML do arquivo
        with open('templates/index.html', 'r', encoding='utf-8') as file:
            HTML = file.read()
        
        conn.close()
        return render_template_string(HTML, 
            empresas=empresas,
            lista_empresas=lista_empresas,
            request=request
        )
        
    except Exception as e:
        logger.error(f"Erro na rota principal: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Erro: {str(e)}", 500

if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
        use_reloader=False
    )
