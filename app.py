# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.middleware.proxy_fix import ProxyFix
import json
import os
import threading
from config import CONFIG_FILE, DOWNLOAD_BASE_DIR
from logger_config import logger
from api import get_token, get_all_companies, get_all_users
from processing import realizar_processamento, TASK_PHRASES_FILE, load_task_phrases
import json as _json
from pathlib import Path

# File used to persist processing status so other worker processes can read it
STATUS_FILE = Path(__file__).resolve().parent / 'processing_status.json'
LOGS_DIR = Path(__file__).resolve().parent / 'logs'

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.secret_key = 'your_secret_key_here'  # Change this to a secure key

def save_task_phrases(fiscal_phrases, contabil_phrases):
    data = {
        "fiscal_phrases": fiscal_phrases,
        "contabil_phrases": contabil_phrases
    }
    try:
        with open(TASK_PHRASES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar frases de tarefas: {e}")
        return False

@app.route('/task_phrases', methods=['GET', 'POST'])
def task_phrases():
    from flask import jsonify
    if request.method == 'GET':
        fiscal, contabil = load_task_phrases()
        return jsonify({
            "fiscal_phrases": fiscal,
            "contabil_phrases": contabil
        })
    elif request.method == 'POST':
        data = request.get_json()
        if not data or "fiscal_phrases" not in data or "contabil_phrases" not in data:
            return jsonify({"error": "Dados inválidos"}), 400
        
        fiscal_phrases = data["fiscal_phrases"]
        contabil_phrases = data["contabil_phrases"]
        
        if not isinstance(fiscal_phrases, list) or not isinstance(contabil_phrases, list):
            return jsonify({"error": "'fiscal_phrases' e 'contabil_phrases' devem ser listas"}), 400
            
        if save_task_phrases(fiscal_phrases, contabil_phrases):
            flash('Frases de tarefas salvas com sucesso!', 'success')
            return jsonify({"message": "Frases de tarefas salvas com sucesso"}), 200
        else:
            flash('Erro ao salvar frases de tarefas.', 'danger')
            return jsonify({"error": "Erro ao salvar frases de tarefas"}), 500

@app.route('/')
def index():
    # Always try to refresh token to avoid 401 errors
    config = load_config()
    credentials = config.get('credentials', {})
    email = credentials.get('email')
    password = credentials.get('password')

    if not email or not password:
        flash('Erro: Credenciais de login não encontradas no arquivo de configuração (gestta_config.json).', 'danger')
        return "<h1>Erro de Configuração</h1><p>Credenciais de login não encontradas no arquivo <code>gestta_config.json</code>.</p>", 500

    # Always get a fresh token to avoid expiration issues
    token = get_token(email=email, password=password)
    if token:
        session['token'] = token
        logger.info(f"Token renovado com sucesso para {email}")
    else:
        flash(f'Erro na autenticação automática com o email {email}. Verifique as credenciais em gestta_config.json e se a API Gestta está acessível.', 'danger')
        return f"<h1>Erro de Autenticação</h1><p>Não foi possível obter um token de acesso com o email {email}.</p>", 500
    
    config = load_config()
    selected_companies = config.get('selected_companies', [])
    selected_users = config.get('selected_users', [])

    # Companies logic with error handling
    all_companies = get_all_companies(session['token']) or []
    if not all_companies:
        logger.warning("Nenhuma empresa foi carregada - possível problema de autenticação ou API")
        flash('Aviso: Não foi possível carregar a lista de empresas. Verifique a conexão com a API.', 'warning')
    
    search_companies_query = request.args.get('search_companies', '').lower()
    if search_companies_query:
        companies = [
            c for c in all_companies 
            if search_companies_query in c.get('name', '').lower() or 
               search_companies_query in c.get('code', '').lower()
        ]
    else:
        companies = all_companies

    # Users logic with error handling
    all_users = get_all_users(session['token']) or []
    if not all_users:
        logger.warning("Nenhum usuário foi carregado - possível problema de autenticação ou API")
        flash('Aviso: Não foi possível carregar a lista de usuários. Verifique a conexão com a API.', 'warning')
    
    search_users_query = request.args.get('search_users', '').lower()
    if search_users_query:
        users = [
            u for u in all_users 
            if search_users_query in u.get('name', '').lower() or 
               search_users_query in u.get('email', '').lower()
        ]
    else:
        users = all_users
        
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    ALLOWED_IP = '177.92.112.194'
    if ip_address != ALLOWED_IP:
        abort(403) # Forbidden
    
    logger.info(f"Carregando página inicial: {len(all_companies)} empresas, {len(all_users)} usuários")
    return render_template(
        'index.html', 
        config=config, 
        companies=all_companies, 
        selected_companies=selected_companies,
        users=all_users,
        selected_users=selected_users,
        ip_address=ip_address
    )



@app.route('/run')
def run():
    if 'token' not in session:
        return redirect(url_for('index'))
    # Start processing in background and expose status via /processing_status
    global _processing_thread, _processing_status
    if '_processing_thread' in globals() and _processing_thread is not None and _processing_thread.is_alive():
        flash('Já existe um processamento em execução.', 'warning')
        return redirect(url_for('index'))

    # capture date params from query string
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    def run_processing():
        try:
            global _processing_status
            _processing_status = {'running': True, 'success': None, 'message': 'Em execução'}
            # persist immediately so other processes/requests can read it
            try:
                STATUS_FILE.write_text(_json.dumps(_processing_status))
            except Exception:
                logger.debug('Não foi possível gravar STATUS_FILE')
            ok = realizar_processamento(start_date=start_date, end_date=end_date)
            # try to attach the latest summary JSON if available
            summary = None
            try:
                if LOGS_DIR.exists():
                    files = sorted(LOGS_DIR.glob('last_run_summary_*.json'))
                    if files:
                        latest = files[-1]
                        summary = _json.loads(latest.read_text())
            except Exception:
                logger.debug('Erro ao carregar summary')
            _processing_status = {'running': False, 'success': bool(ok), 'message': 'Concluído' if ok else 'Concluído com erros', 'summary': summary}
            try:
                STATUS_FILE.write_text(_json.dumps(_processing_status))
            except Exception:
                logger.debug('Não foi possível gravar STATUS_FILE')
        except Exception as e:
            logger.error(f"Erro ao executar processamento: {e}")
            _processing_status = {'running': False, 'success': False, 'message': str(e)}
            try:
                STATUS_FILE.write_text(_json.dumps(_processing_status))
            except Exception:
                logger.debug('Não foi possível gravar STATUS_FILE')

    _processing_thread = threading.Thread(target=run_processing)
    _processing_thread.start()
    _processing_status = {'running': True, 'success': None, 'message': 'Em execução'}
    try:
        STATUS_FILE.write_text(_json.dumps(_processing_status))
    except Exception:
        logger.debug('Não foi possível gravar STATUS_FILE')
    flash('Processamento iniciado em background!', 'info')
    return redirect(url_for('index'))


@app.route('/processing_status')
def processing_status():
    # Return a small JSON about current processing state
    from flask import jsonify
    # Prefer file-backed status if available (works across processes)
    try:
        if STATUS_FILE.exists():
            txt = STATUS_FILE.read_text()
            try:
                return jsonify(_json.loads(txt))
            except Exception:
                pass
    except Exception:
        logger.debug('Erro ao ler STATUS_FILE')
    status = globals().get('_processing_status', {'running': False, 'success': None, 'message': 'Nenhuma execução'} )
    return jsonify(status)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        download_dir = request.form['download_dir']
        debug_mode = 'debug_mode' in request.form
        # Save settings
        config = load_config()
        config['settings']['download_dir'] = download_dir
        config['settings']['debug_mode'] = debug_mode
        save_config(config)
        flash('Configurações salvas!', 'success')
        return redirect(url_for('settings'))
    config = load_config()
    return render_template('settings.html', config=config)

@app.route('/save_selection', methods=['POST'])
def save_selection():
    if 'token' not in session:
        return redirect(url_for('index'))
    selected_companies = request.form.getlist('companies')
    selected_users = request.form.getlist('users')
    config = load_config()
    config['selected_companies'] = selected_companies
    config['selected_users'] = selected_users
    save_config(config)
    flash('Seleção salva!', 'success')
    return redirect(url_for('index'))


@app.route('/config_preview')
def config_preview():
    """Return current config JSON for preview in the frontend."""
    if 'token' not in session:
        return redirect(url_for('index'))
    config = load_config()
    # Return as JSON response
    from flask import jsonify
    return jsonify(config)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "credentials": {"email": "", "password": ""},
        "settings": {"debug_mode": True, "download_dir": DOWNLOAD_BASE_DIR},
        "selected_companies": [],
        "selected_users": []
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5010)
