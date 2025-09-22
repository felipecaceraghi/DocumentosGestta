# api.py
import requests, time, os, re
from datetime import datetime
from logger_config import logger
from file_utils import sanitize_filename, truncate_name, iso_to_mes_ano, safe_move_folder, count_files_in_folder, monta_caminho_contabil, monta_caminho_fiscal, extract_all_archives, extract_archive
from config import DEBUG_MODE, DOWNLOAD_BASE_DIR, GESTTA_EMAIL, GESTTA_PASSWORD
import shutil

# Desativar avisos SSL e configurar o ambiente para ignorar certificados problemáticos
# Isto é necessário quando o Fiddler ou outros proxies SSL estão instalados
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['PYTHONHTTPSVERIFY'] = '0'  # Para subprocessos 

# Função para criar uma sessão com verificação SSL desativada
def create_session():
    session = requests.Session()
    session.verify = False  # Desabilita verificação SSL
    return session

def get_token(email=None, password=None):
    """
    Faz login na API do Gestta e retorna o token de autorização.
    Aceita credenciais como parâmetros ou usa as variáveis globais como backup.
    """
    # Usar parâmetros fornecidos ou recorrer às variáveis globais
    use_email = email if email is not None else GESTTA_EMAIL
    use_password = password if password is not None else GESTTA_PASSWORD
    
    logger.info(f"Tentando login com email: {use_email}")
    logger.info(f"Senha possui {len(use_password)} caracteres")
    
    login_url = "https://api.gestta.com.br/core/login"
    payload = {"email": use_email, "password": use_password}
    headers = {"Accept": "application/json, text/plain, */*", "Content-Type": "application/json;charset=UTF-8"}
    
    try:
        # Usar sessão com verificação SSL desativada
        session = create_session()
        response = session.post(login_url, json=payload, headers=headers, timeout=30)
        logger.info(f"Request Body: {response.request.body}")
        logger.info(f"Request Headers: {response.request.headers}")
        logger.info(f"Response Status: {response.status_code}")
        logger.info(f"Response Text: {response.text}")

        if response.status_code == 200:
            token = response.headers.get("authorization") or response.headers.get("Authorization")
            if token:
                logger.info("Token obtido com sucesso.")
                return token
            else:
                logger.error("Token não encontrado na resposta.")
                return None
        else:
            logger.error(f"Erro no login: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exceção ao obter token: {str(e)}")
        return None

def get_all_companies(token, company_ids=None):
    url = "https://api.gestta.com.br/core/customer"
    headers = {"Authorization": token, "Accept": "application/json, text/plain, */*"}
    try:
        session = create_session()
        response = session.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "docs" in data:
                companies = data["docs"]
                if company_ids:
                    companies = [c for c in companies if c.get("_id") in company_ids]
                logger.info(f"{len(companies)} empresas carregadas.")
                return companies
            else:
                logger.error("Chave 'docs' não encontrada no retorno de empresas.")
                return []
        else:
            logger.error(f"Erro ao obter empresas: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        logger.error(f"Exceção ao buscar empresas: {str(e)}")
        return []

def get_all_users(token, user_ids=None):
    url = "https://api.gestta.com.br/core/company/user"
    headers = {"Authorization": token, "Accept": "application/json, text/plain, */*"}
    all_users = []
    page = 1
    try:
        session = create_session()
        while True:
            params = {"page": page, "limit": 1000}
            response = session.get(url, headers=headers, params=params)
            if response.status_code != 200:
                if response.status_code == 401:
                    logger.error(f"Token expirado ou inválido ao buscar usuários na página {page}: {response.status_code}")
                else:
                    logger.error(f"Erro na página {page}: {response.status_code}")
                break
            data = response.json()
            docs = data.get("docs", [])
            logger.info(f"Página {data.get('page', page)}: {len(docs)} usuários.")
            all_users.extend(docs)
            total_pages = data.get("pages")
            if total_pages and page >= total_pages:
                break
            page += 1
            time.sleep(0.5)
        if user_ids:
            all_users = [u for u in all_users if u.get("_id") in user_ids]
        logger.info(f"Total de usuários: {len(all_users)}")
        return all_users
    except Exception as e:
        logger.error(f"Exceção ao buscar usuários: {str(e)}")
        return []

def search_all_customer_tasks(token, customer_ids, company_user_ids, start_date, end_date):
    url = "https://api.gestta.com.br/core/customer/task/search"
    headers = {
        "Authorization": token,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8"
    }
    page = 1
    limit = 100000
    all_tasks = []
    try:
        session = create_session()
        while True:
            payload = {
                "status": ["OPEN", "IMPEDIMENT"],
                "type": ["SERVICE_ORDER", "RECURRENT", "ACCOUNTING"],
                "company_user": company_user_ids,
                "start_date": start_date,
                "end_date": end_date,
                "date_type": "DUE_DATE",
                "no_owner": False,
                "os_workflow": True,
                "os_free": False,
                "page": page,
                "limit": limit
            }
            if customer_ids:
                payload["customer"] = customer_ids
            response = session.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"Erro na pesquisa na página {page}: {response.status_code} - {response.text}")
                break
            data = response.json()
            docs = data.get("docs", [])
            logger.info(f"Página {page}: {len(docs)} tarefas retornadas.")
            if not docs:
                break
            all_tasks.extend(docs)
            page += 1
            time.sleep(0.5)
        logger.info(f"Total de tarefas coletadas: {len(all_tasks)}")
        return all_tasks
    except Exception as e:
        logger.error(f"Exceção ao buscar tarefas: {str(e)}")
        return []

def get_task_detail(token, task_id):
    url = f"https://api.gestta.com.br/core/customer/task/{task_id}"
    headers = {"Authorization": token, "Accept": "application/json, text/plain, */*"}
    try:
        session = create_session()
        response = session.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Erro ao buscar detalhe da task {task_id}: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Exceção ao buscar detalhe da task {task_id}: {str(e)}")
        return None

def download_document_file(token, task_id, doc_id, customer_id, file_obj, target_folder):
    file_id = file_obj.get("_id", "")
    file_name = file_obj.get("file_name", f"{file_id}.dat")
    safe_file_name = sanitize_filename(file_name)
    local_path = os.path.join(target_folder, safe_file_name)
    if len(local_path) > 250:
        file_extension = os.path.splitext(safe_file_name)[1]
        shortened_name = f"{file_id}{file_extension}"
        local_path = os.path.join(target_folder, shortened_name)
        logger.warning(f"Nome de arquivo muito longo, renomeando para: {shortened_name}")
    try:
        payload = {
            "customer_task": task_id, 
            "document": doc_id, 
            "customer": customer_id, 
            "file": file_id
        }
        download_url = "https://api.gestta.com.br/accounting/pendency/document/download"
        headers = {
            "Authorization": token,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8"
        }
        session = create_session()
        resp = session.post(download_url, json=payload, headers=headers)
        if resp.status_code == 200:
            try:
                resp_data = resp.json()
                link = resp_data.get("link", "")
            except Exception:
                link = resp.text.strip()
            if link:
                download_resp = session.get(link, stream=True, timeout=120)
                if download_resp.status_code == 200:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    with open(local_path, 'wb') as f:
                        for chunk in download_resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    logger.info(f"Arquivo salvo: {local_path}")
                    return f"Arquivo salvo: {local_path}"
                else:
                    error_msg = f"Erro ao baixar (ID: {file_id}): {download_resp.status_code}"
                    logger.error(error_msg)
                    return error_msg
            else:
                error_msg = f"Link não retornado (ID: {file_id})."
                logger.error(error_msg)
                return error_msg
        else:
            error_msg = f"Erro na requisição de download (ID: {file_id}): {resp.status_code}"
            logger.error(error_msg)
            return error_msg
    except Exception as ex:
        error_msg = f"Exceção (ID: {file_id}): {ex}"
        logger.error(error_msg)
        return error_msg

def send_task_comment(token, task_id, competence="XX/XXXX", customer_id=None, company_department=None):
    """
    Envia um comentário para uma tarefa com mensagem fixa, incorporando a competência dinâmica.
    Antes do envio, realiza uma requisição GET para obter o accountable (customer_user) de forma dinâmica.
    Suporta múltiplos usuários responsáveis (accountables).
    
    Args:
        token (str): Token de autenticação.
        task_id (str): ID da tarefa.
        competence (str, optional): Competência a ser inserida na mensagem. Padrão "XX/XXXX".
        customer_id (str): ID do customer (necessário para buscar o accountable).
        company_department (str): ID do departamento (necessário para buscar o accountable).
        
    Returns:
        str: Mensagem informando sucesso ou erro.
    """
    if DEBUG_MODE:
        logger.info("[DEBUG] Comentário simulado mas não enviado pois DEBUG_MODE=True.")
        return "[DEBUG] Comentário simulado"
    
    if not customer_id or not company_department:
        error_msg = "customer_id e company_department devem ser informados."
        logger.error(error_msg)
        return error_msg
    
    # Chamada GET para obter o accountable (customer_user)
    accountable_url = f"https://api.gestta.com.br/admin/customer/{customer_id}/accountable?company_department={company_department}"
    get_headers = {
        "Authorization": token,
        "Accept": "application/json, text/plain, */*"
    }
    try:
        session = create_session()
        get_response = session.get(accountable_url, headers=get_headers)
        if get_response.status_code == 200:
            accountable_data = get_response.json()
            if isinstance(accountable_data, list) and len(accountable_data) > 0:
                # Processa TODOS os usuários responsáveis, não apenas o primeiro
                customer_user_ids = []
                for accountable in accountable_data:
                    if "customer_user" in accountable and "_id" in accountable["customer_user"]:
                        customer_user_ids.append(accountable["customer_user"]["_id"])
                        logger.info(f"Adicionando usuário {accountable['customer_user'].get('name', 'Unknown')} à notificação")
                
                if not customer_user_ids:
                    error_msg = "Nenhum customer_user._id encontrado nos accountables."
                    logger.error(error_msg)
                    return error_msg
            else:
                error_msg = "Nenhum accountable retornado pela API."
                logger.error(error_msg)
                return error_msg
        else:
            error_msg = f"Erro ao buscar accountable: {get_response.status_code} - {get_response.text}"
            logger.error(error_msg)
            return error_msg
    except Exception as e:
        error_msg = f"Exceção ao buscar accountable: {str(e)}"
        logger.error(error_msg)
        return error_msg
    
    # Montagem da mensagem dinâmica baseada na competência
    message_html = (
        "<p>Prezado Cliente,</p>"
        "<p>&nbsp;</p>"
        f"<p>Verificamos que a documentação referente à competência {competence} não foi anexada ou foi enviada de forma incompleta no Gestta. "
        "Conforme estabelecido em contrato, o envio da documentação dentro do prazo acordado é essencial para garantir a entrega do fechamento contábil "
        "sem atrasos e evitar a incidência de juros e multas por vencimento de impostos.</p>"
        "<p>&nbsp;</p>"
        "<p>Diante disso, seguiremos com o fechamento e a apuração dos impostos com as informações disponíveis. Eventuais penalidades decorrentes "
        "de dados não enviados serão de inteira responsabilidade da empresa.</p>"
        "<p>&nbsp;</p>"
        "<p>Ficamos à disposição para esclarecer qualquer dúvida.</p>"
        "<p>&nbsp;</p>"
        "<p>Atenciosamente,</p>"
        "<p>⬛🟦🟩🟧🟨</p>"
        "<p>Go Further - Sempre à frente</p>"
    )
    
    # Montagem da URL e do payload para o envio do comentário
    url = f"https://api.gestta.com.br/core/customer/task/{task_id}/history/comment"
    post_headers = {
        "Authorization": token,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8"
    }
    payload = {
        "files": [],
        "external": True,
        "message": message_html,
        # Usa TODOS os customer_user_ids retornados na chamada GET
        "mentions": customer_user_ids,
        "cc_mentions": []
    }
    
    logger.info(f"Enviando comentário para {len(customer_user_ids)} usuário(s)")
    
    try:
        post_response = session.post(url, json=payload, headers=post_headers)
        if post_response.status_code in (200, 201):
            logger.info(f"Comentário enviado com sucesso para {len(customer_user_ids)} usuário(s).")
            return "Comentário enviado com sucesso."
        else:
            error_msg = f"Erro ao enviar comentário: {post_response.status_code} - {post_response.text}"
            logger.error(error_msg)
            return error_msg
    except Exception as e:
        error_msg = f"Exceção ao enviar comentário: {str(e)}"
        logger.error(error_msg)
        return error_msg

def tarefa_possui_arquivos(task_detail, verificar_completo=False):
    """
    Verifica se uma tarefa possui documentos anexados, baseado na presença do campo 'last_upload_date'.
    
    Args:
        task_detail (dict): Detalhes da tarefa
        verificar_completo (bool): Se True, verifica se todos os documentos solicitados têm uploads.
                                  Se False, verifica se qualquer documento tem upload.
    
    Returns:
        bool: True se a condição for atendida, False caso contrário.
    """
    if not task_detail:
        return False
    
    # Verificar a estrutura de document_request
    doc_req = task_detail.get("document_request", {})
    req_docs = doc_req.get("requested_documents", [])
    
    if not req_docs:
        # Se não há documentos solicitados, consideramos completo
        logger.info("Nenhum documento solicitado encontrado. Considerando tarefa completa.")
        return True
    
    # Contar documentos com upload e total de documentos não ignorados
    docs_com_upload = 0
    docs_validos = 0
    
    for doc in req_docs:
        # Ignorar documentos marcados como "disconsidered"
        if doc.get("disconsidered", False):
            logger.debug(f"Documento '{doc.get('name', 'sem nome')}' está marcado como desconsiderado")
            continue
        
        docs_validos += 1
        
        # Verificar se tem last_upload_date
        if "last_upload_date" in doc:
            docs_com_upload += 1
            logger.debug(f"Documento '{doc.get('name', 'sem nome')}' tem data de upload: {doc.get('last_upload_date')}")
        else:
            logger.debug(f"Documento '{doc.get('name', 'sem nome')}' não tem data de upload")
    
    # Se não há documentos válidos (todos foram desconsiderados), consideramos completo
    if docs_validos == 0:
        logger.info("Todos os documentos estão marcados como desconsiderados. Considerando tarefa completa.")
        return True
    
    # Verificar se todos os documentos têm upload ou se pelo menos um tem upload
    if verificar_completo:
        resultado = docs_com_upload == docs_validos
        logger.info(f"Verificação completa: {docs_com_upload}/{docs_validos} documentos com upload. Resultado: {resultado}")
        return resultado
    else:
        resultado = docs_com_upload > 0
        logger.info(f"Verificação parcial: {docs_com_upload}/{docs_validos} documentos com upload. Resultado: {resultado}")
        return resultado

def download_all_task_documents(token, task_id, customer_id, target_folder):
    """
    Baixa todos os documentos de uma tarefa de uma vez só usando o endpoint download/all
    Retorna o caminho do arquivo ZIP baixado ou None em caso de erro
    """
    try:
        # Passo 1: Obter o document identifier
        url = "https://api.gestta.com.br/accounting/pendency/document/download/all"
        headers = {
            "Authorization": token,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8"
        }
        
        payload = {
            "customer_task": task_id
        }
        
        logger.info(f"[DOWNLOAD] Solicitando document identifier para tarefa {task_id}")
        session = create_session()
        response = session.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            try:
                # Obter o document identifier da resposta
                resp_data = response.json()
                document_identifier = resp_data.get("documentIdentifier")
                
                if not document_identifier:
                    logger.error("Document identifier não retornado pela API")
                    return None
                
                logger.info(f"[DOWNLOAD] Document identifier obtido: {document_identifier}")
                
                # Passo 2: Fazer a requisição para verificar o status e obter a URL final do download
                status_url = f"https://api.gestta.com.br/core/customer/task/document/download/{document_identifier}"
                status_headers = {
                    "Authorization": token,
                    "Accept": "application/json, text/plain, */*"
                }
                
                # Polling para verificar quando o ZIP estiver pronto
                max_attempts = 30  # Máximo de tentativas
                attempt = 0
                wait_time = 2  # Tempo inicial de espera em segundos
                
                logger.info(f"[DOWNLOAD] Aguardando preparação do arquivo ZIP para tarefa {task_id}...")
                
                while attempt < max_attempts:
                    attempt += 1
                    status_response = session.get(status_url, headers=status_headers)
                    
                    if status_response.status_code == 200:
                        try:
                            status_data = status_response.json()
                            status = status_data.get("status")
                            
                            if status == "DONE":
                                # ZIP está pronto, obter a URL
                                download_url = status_data.get("url")
                                if not download_url:
                                    logger.error("URL de download não encontrada na resposta")
                                    logger.debug(f"Resposta completa: {status_data}")
                                    return None
                                
                                logger.info(f"[DOWNLOAD] ZIP pronto após {attempt} verificações. Baixando...")
                                
                                # Garantir que o caminho não tenha espaços no final - correção crítica
                                target_folder = target_folder.rstrip()
                                
                                # Criar um caminho de diretório seguro para o arquivo ZIP
                                safe_dir = target_folder.replace(" ", "_").rstrip()
                                
                                # Garantir que não há caracteres problemáticos no caminho
                                safe_dir = re.sub(r'[^\w\\:/_-]', '_', safe_dir)
                                
                                # Se o safe_dir é diferente do target_folder, criar nova pasta
                                if safe_dir != target_folder:
                                    logger.info(f"Usando diretório seguro: {safe_dir} em vez de {target_folder}")
                                    try:
                                        os.makedirs(safe_dir, exist_ok=True)
                                    except Exception as e:
                                        logger.error(f"Erro ao criar diretório seguro: {e}")
                                        # Usar diretório temporário como fallback
                                        safe_dir = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"gestta_download_{task_id}")
                                        os.makedirs(safe_dir, exist_ok=True)
                                        logger.info(f"Usando diretório temporário: {safe_dir}")
                                
                                # Usar um nome de arquivo simples sem espaços ou caracteres especiais
                                zip_filename = f"task_{task_id}.zip"
                                
                                # Criar o caminho completo do arquivo ZIP sem espaços
                                zip_path = os.path.join(safe_dir, zip_filename)
                                
                                # Remover qualquer espaço extra que possa ter surgido
                                zip_path = zip_path.replace(" ", "_").rstrip()
                                
                                # Normalizar o caminho para garantir consistência
                                zip_path = os.path.abspath(os.path.normpath(zip_path))
                                
                                # Criar diretório pai se necessário (evita erro de diretório não encontrado)
                                os.makedirs(os.path.dirname(zip_path), exist_ok=True)
                                
                                # Verificar se o arquivo já existe e removê-lo
                                if os.path.exists(zip_path):
                                    try:
                                        os.remove(zip_path)
                                        logger.info(f"Arquivo existente removido: {zip_path}")
                                    except Exception as e:
                                        logger.error(f"Erro ao remover arquivo existente: {e}")
                                
                                # Log detalhado para diagnóstico
                                logger.info(f"[DOWNLOAD] Caminho final do arquivo ZIP: {zip_path}")
                                
                                # Baixar o arquivo
                                try:
                                    # Testar a escrita na pasta com um arquivo temporário
                                    test_file = os.path.join(os.path.dirname(zip_path), "test_write.tmp")
                                    try:
                                        with open(test_file, 'w') as f:
                                            f.write("test")
                                        os.remove(test_file)
                                        logger.info(f"Teste de escrita bem-sucedido em: {os.path.dirname(zip_path)}")
                                    except Exception as e:
                                        logger.error(f"Teste de escrita falhou: {e}")
                                        # Tentar diretório temporário como fallback
                                        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
                                        zip_path = os.path.join(temp_dir, f"gestta_task_{task_id}.zip")
                                        logger.info(f"Usando caminho alternativo: {zip_path}")
                                    
                                    # Baixar o arquivo
                                    logger.info(f"[DEBUG] Attempting to download from: {download_url}")
                                    download_resp = session.get(download_url, stream=True, timeout=3600)
                                    
                                    if download_resp.status_code == 200:
                                        try:
                                            with open(zip_path, 'wb') as f:
                                                for chunk in download_resp.iter_content(chunk_size=8192):
                                                    if chunk:
                                                        f.write(chunk)
                                            logger.info(f"[DOWNLOAD] Arquivo ZIP salvo com sucesso em: {zip_path}")
                                            
                                            if os.path.exists(zip_path):
                                                return zip_path
                                            else:
                                                logger.error(f"Arquivo ZIP não foi criado apesar de não haver erros: {zip_path}")
                                                return None
                                        except Exception as write_error:
                                            logger.error(f"Erro ao escrever arquivo ZIP: {str(write_error)}")
                                            return None
                                    else:
                                        logger.error(f"Erro ao baixar ZIP completo: {download_resp.status_code}")
                                        return None
                                except Exception as download_error:
                                    logger.error(f"Erro durante o download do arquivo ZIP: {str(download_error)}")
                                    return None
                            
                            elif status == "ERROR":
                                logger.error("Erro reportado pelo servidor ao preparar o ZIP")
                                return None
                            else:
                                logger.info(f"[DOWNLOAD] Status atual: {status}, aguardando... (tentativa {attempt}/{max_attempts})")
                                time.sleep(wait_time)
                                if wait_time < 30:
                                    wait_time = min(wait_time * 1.5, 30)
                            
                        except Exception as e:
                            logger.error(f"Erro ao processar resposta de status: {str(e)}")
                            time.sleep(wait_time)
                    else:
                        logger.error(f"Erro ao verificar status: {status_response.status_code}")
                        if status_response.status_code == 404:
                            logger.info(f"[DOWNLOAD] Endpoint não encontrado, tentativa {attempt}. Aguardando...")
                        time.sleep(wait_time)
                
                logger.error(f"Tempo limite excedido aguardando preparação do ZIP após {max_attempts} tentativas")
                return None
            
            except Exception as e:
                logger.error(f"Erro ao processar resposta da API: {str(e)}")
                return None
        else:
            logger.error(f"Erro ao solicitar download completo: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exceção ao baixar todos os documentos: {str(e)}")
        return None

def process_task_documents(token, task_detail, debug_mode=False, download_dir=None):
    """
    Processa e baixa documentos relacionados a uma tarefa
    
    Args:
        token (str): Token de autenticação
        task_detail (dict): Detalhes da tarefa
        debug_mode (bool): Se está em modo debug
        download_dir (str): Diretório específico para download dos arquivos
        
    Returns:
        int: Número de documentos baixados
    """
    if not task_detail:
        logger.error("Detalhe da tarefa não fornecido.")
        return 0
    
    task_name = task_detail.get("name", "task_default")
    task_id = task_detail.get("_id", "")
    customer = task_detail.get("customer", {})
    customer_id = customer.get("_id", "")
    customer_code = customer.get("code", "SEM_CODE")
    date_field = task_detail.get("competence_date")
    lower_name = task_name.lower()
    
    if not tarefa_possui_arquivos(task_detail):
        logger.warning(f"[SKIP] Tarefa {task_id} ({task_name}) não possui documentos para download.")
        return 0
    
    if "fiscais" in lower_name:
        path_func = monta_caminho_fiscal
    else:
        path_func = monta_caminho_contabil
        
    if date_field:
        mes_ano = iso_to_mes_ano(date_field)
    else:
        mes_ano = ("00", "0000")
        
    task_name_safe = sanitize_filename(truncate_name(task_name, 50))
    task_name_safe = task_name_safe.rstrip()
    
    # Criar uma versão ainda mais segura do nome para a pasta
    task_name_very_safe = re.sub(r'[^\w\-]', '_', task_name_safe)   
    
    # Adicionar timestamp para evitar sobreposição quando há tarefas com mesmo nome
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    task_name_with_timestamp = f"{task_name_very_safe}_{timestamp}"
    
    base_dir = download_dir or DOWNLOAD_BASE_DIR
    base_dir = base_dir.rstrip()
    
    logger.info(f"Diretório base para download: {base_dir}")
    
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
        logger.info(f"Criado diretório base de download: {base_dir}")
        
    if not os.access(base_dir, os.W_OK):
        logger.error(f"Sem permissões de escrita no diretório base: {base_dir}")
        return 0
    
    # Usar nome com timestamp para criar a pasta
    task_folder = os.path.normpath(os.path.join(base_dir, task_name_with_timestamp))
    task_folder = task_folder.rstrip()
    
    # Adicionar verificação extra para garantir que o caminho não termina com espaço
    if task_folder.endswith(" "):
        task_folder = task_folder.rstrip()
        logger.warning(f"Caminho com espaço no final corrigido: {task_folder}")
    
    logger.info(f"Pasta específica para a tarefa: {task_folder}")
    
    try:
        os.makedirs(task_folder, exist_ok=True)
        logger.info(f"Pasta para download criada: {task_folder}")
    except Exception as e:
        logger.error(f"Erro ao criar pasta para download {task_folder}: {e}")
        return 0
    
    logger.info(f"[DOWNLOAD] Solicitando download de todos os documentos da tarefa {task_id}")
    
    zip_file_path = download_all_task_documents(token, task_id, customer_id, task_folder)
    
    if not zip_file_path:
        logger.warning(f"Download em lote falhou para tarefa {task_id}. Não há documentos para processar.")
        return 0
    
    if not os.path.exists(zip_file_path):
        logger.error(f"Arquivo ZIP não encontrado após download: {zip_file_path}")
        return 0
    
    logger.info(f"[DOWNLOAD] Iniciando extração de arquivos em: {task_folder}")
    try:
        # A função extract_all_archives vai encontrar o ZIP baixado e quaisquer outros arquivos
        extract_all_archives(task_folder)
        logger.info(f"[DOWNLOAD] Extração concluída em {task_folder}")
        
        final_count = count_files_in_folder(task_folder)
        
        if final_count == 0:
            logger.warning(f"Nenhum arquivo encontrado após a extração para a tarefa {task_id}")
            return 0
            
        logger.info(f"[DOWNLOAD] {final_count} arquivos no total para a tarefa {task_id}")
        
        destino_base = path_func(customer_code, mes_ano)
        if destino_base:
            try:
                os.makedirs(destino_base, exist_ok=True)
                dest_path = os.path.normpath(os.path.join(destino_base, os.path.basename(task_folder)))
                
                moved_count = safe_move_folder(task_folder, dest_path, DEBUG_MODE)
                logger.info(f"Arquivos pós-extração para '{task_name}': {moved_count}")
                
                return moved_count
            except Exception as e:
                logger.error(f"Erro ao mover pasta {task_folder} para {destino_base}: {e}")
                return final_count
        else:
            logger.warning(f"Caminho de destino não definido para {customer_code}. Pasta não movida.")
            logger.info(f"Arquivos pós-extração para '{task_name}': {final_count}")
            
            return final_count
            
    except Exception as e:
        logger.error(f"Erro durante o processo de extração em {task_folder}: {e}")
        return 0

def update_task_status(token, task_id, new_status="DONE"):
    """
    Altera o status de uma tarefa para o valor especificado.
    
    Args:
        token (str): Token de autenticação.
        task_id (str): ID da tarefa.
        new_status (str, optional): Novo status. Padrão "DONE".
        
    Returns:
        str: Mensagem informando sucesso ou erro.
    """
    url = f"https://api.gestta.com.br/es/task/{task_id}/status"
    payload = {"status": new_status}
    headers = {
        "Authorization": token,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8"
    }
    try:
        session = create_session()
        response = session.put(url, json=payload, headers=headers)
        if response.status_code == 200:
            logger.info(f"Status da tarefa {task_id} alterado para '{new_status}' com sucesso.")
            return f"Status da tarefa alterado para '{new_status}' com sucesso."
        else:
            error_msg = f"Erro ao alterar status da tarefa {task_id}: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return error_msg
    except Exception as e:
        error_msg = f"Exceção ao alterar status da tarefa {task_id}: {str(e)}"
        logger.error(error_msg)
        return error_msg

if __name__ == "__main__":
    import os
    import json
    from processing import get_token  # Certifique-se de que a função get_token está definida em processing.py
    
    config_file = os.path.join(os.path.dirname(__file__), "gestta_config.json")
    if not os.path.exists(config_file):
        print("Arquivo de configuração 'gestta_config.json' não encontrado.")
        exit(1)
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    email = config.get("credentials", {}).get("email", "")
    password = config.get("credentials", {}).get("password", "")
    
    token = get_token(email, password)
    if not token:
        print("Falha ao obter token.")
        exit(1)
    
    # Task ID fixo conforme informado
    task_id = "67ed605064af71a76a719326"
    
    # Mensagem HTML inventada para teste
    competence = "01/2023"
    resultado = send_task_comment(token, task_id, competence)
    print(resultado)
