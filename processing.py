# processing.py
import os, sys, json, shutil
import time as pytime  # Renomeie para evitar conflito
from datetime import datetime, date, timedelta, time
import schedule
from logger_config import logger
from config import CONFIG_FILE, DOWNLOAD_BASE_DIR, DEBUG_MODE
from api import (get_token, get_all_companies, get_all_users, search_all_customer_tasks,
                 get_task_detail, process_task_documents, update_task_status)
# from dashboard import gerar_dashboard_estatisticas
import subprocess
from file_utils import sanitize_filename, truncate_name, iso_to_mes_ano, safe_move_folder, monta_caminho_contabil, monta_caminho_fiscal
from debug_utils import create_task_debug_folder
import config as config_module
from pathlib import Path

TASK_PHRASES_FILE = Path(__file__).resolve().parent / 'task_phrases.json'

def load_task_phrases():
    try:
        if TASK_PHRASES_FILE.exists():
            with open(TASK_PHRASES_FILE, 'r', encoding='utf-8') as f:
                phrases = json.load(f)
                return phrases.get('fiscal_phrases', []), phrases.get('contabil_phrases', [])
        else:
            logger.warning(f"Arquivo de frases de tarefas não encontrado: {TASK_PHRASES_FILE}. Usando frases padrão.")
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar {TASK_PHRASES_FILE}: {e}. Usando frases padrão.")
    except Exception as e:
        logger.error(f"Erro ao carregar frases de tarefas: {e}. Usando frases padrão.")
    return [], [] # Default empty lists

def carregar_configuracoes():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        import config as config_module
        
        if "settings" in config:
            settings = config["settings"]
            if "debug_mode" in settings:
                config_module.DEBUG_MODE = settings["debug_mode"]
            if "download_dir" in settings:
                config_module.DOWNLOAD_BASE_DIR = settings["download_dir"]
                os.makedirs(config_module.DOWNLOAD_BASE_DIR, exist_ok=True)
        
        if "credentials" in config:
            creds = config["credentials"]
            email = creds.get("email", "")
            password = creds.get("password", "")
            token = get_token(email=email, password=password)
        else:
            token = get_token()
            logger.info(f"Credenciais carregadas: Email={config_module.GESTTA_EMAIL}, Senha=[{len(config_module.GESTTA_PASSWORD)} caracteres]")
        
        return config.get("selected_companies", []), config.get("selected_users", [])
    except Exception as e:
        logger.error(f"Erro ao carregar configurações: {e}")    
        raise

def realizar_processamento(start_date=None, end_date=None, force_execution=False):
    """
    Realiza o processamento de busca e download de documentos do Gestta.
    
    Args:
        start_date (str, optional): Data inicial no formato YYYY-MM-DD para busca de tarefas.
        end_date (str, optional): Data final no formato YYYY-MM-DD para busca de tarefas.
        force_execution (bool, optional): Parâmetro mantido para compatibilidade, mas não utilizado.
    
    Returns:
        bool: True se o processamento foi concluído com sucesso, False caso contrário.
    """
    start_processing_time = pytime.time()  # Aqui mudamos de time.time() para pytime.time()
    logger.info("===== INICIANDO PROCESSAMENTO =====")
    
    estatisticas = {
        "tarefas_verificadas": 0,
        "tarefas_filtradas": 0,
        "tarefas_sem_documentos": 0,
        "alertas_enviados": 0,
        "tarefas_processadas_com_sucesso": 0,
        "documentos_baixados": 0,
        "tempo_total": 0,
        "empresas_carregadas": 0,
        "empresas_processadas": 0,
        "tarefas_concluidas": 0,
        "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        selected_companies, selected_users = carregar_configuracoes()
        
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        email = config.get("credentials", {}).get("email", "")
        password = config.get("credentials", {}).get("password", "")
        
        logger.info(f"Modo DEBUG: {'Ativado' if DEBUG_MODE else 'Desativado'}")
        logger.info(f"Diretório de download: {DOWNLOAD_BASE_DIR}")

        token = get_token(email=email, password=password)
        
        if not token:
            logger.error("Erro ao obter token. Encerrando.")
            return False

        companies = get_all_companies(token, selected_companies)
        users = get_all_users(token, selected_users)
        
        estatisticas["empresas_carregadas"] = len(companies)
        
        empresas_com_documentos = set()
        
        logger.info(f"Processando {len(companies)} empresas e {len(users)} usuários")
        if not companies or not users:
            logger.error("Nenhuma empresa ou usuário selecionado. Execute o Configurador Gestta primeiro.")
            return False
        company_ids = [c["_id"] for c in companies if "_id" in c]
        user_ids = [u["_id"] for u in users if "_id" in u]

        alert_date = date.today() 
        if start_date:
            try:
                alert_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Formato de data inválido: {start_date}. Usando data atual.")
        
        alert_date_str_ini = alert_date.strftime("%Y-%m-%d") + "T00:00:00-03:00"
        alert_date_str_fim = alert_date.strftime("%Y-%m-%d") + "T23:59:59-03:00"
        
        logger.info(f"[PROCESSAMENTO] Buscando tarefas com vencimento hoje: {alert_date.strftime('%d/%m/%Y')}")
        
        tasks_today = search_all_customer_tasks(token, company_ids, user_ids, alert_date_str_ini, alert_date_str_fim)
        estatisticas["tarefas_verificadas"] = len(tasks_today)

        fiscal_phrases, contabil_phrases = load_task_phrases()
        all_phrases = fiscal_phrases + contabil_phrases
        filtered_tasks = []
        
        for task in tasks_today:
            name_lower = task.get("name", "").lower()
            if any(phrase in name_lower for phrase in all_phrases):
                filtered_tasks.append(task)
        
        logger.info(f"Encontradas {len(filtered_tasks)} tarefas de cobrança de documentos com vencimento hoje")
        estatisticas["tarefas_filtradas"] = len(filtered_tasks)
        
        for task in filtered_tasks:
            task_id = task.get("_id")
            task_name = task.get("name", "")
            
            logger.info(f"Processando tarefa: {task_name} (ID: {task_id})")
            
            detail = get_task_detail(token, task_id)
            if not detail:
                logger.error(f"Não foi possível obter detalhes da tarefa {task_id}. Pulando.")
                continue
            
            from api import tarefa_possui_arquivos
            tem_documentos_completos = tarefa_possui_arquivos(detail, verificar_completo=True)
            tem_alguns_documentos = tarefa_possui_arquivos(detail, verificar_completo=False)
            
            competencia = "XX/XXXX"
            if date_field := detail.get("competence_date"):
                try:
                    data_competencia = datetime.fromisoformat(date_field.replace("Z", "+00:00"))
                    competencia = f"{data_competencia.month:02d}/{data_competencia.year}"
                except Exception as e:
                    logger.warning(f"Erro ao extrair data de competência: {e}")
            
            if tem_documentos_completos:
                logger.info(f"Tarefa {task_id} possui todos os documentos. Realizando download.")
                docs_baixados = process_task_documents(token, detail, debug_mode=DEBUG_MODE)
                estatisticas["documentos_baixados"] += docs_baixados
                estatisticas["tarefas_processadas_com_sucesso"] += 1 if docs_baixados > 0 else 0
                
            elif tem_alguns_documentos:
                logger.info(f"Tarefa {task_id} possui documentos parciais. Baixando disponíveis e enviando aviso.")
                docs_baixados = process_task_documents(token, detail, debug_mode=DEBUG_MODE)
                estatisticas["documentos_baixados"] += docs_baixados
                estatisticas["tarefas_processadas_com_sucesso"] += 1 if docs_baixados > 0 else 0
                
                from api import send_task_comment
                
                tipo_fechamento = "contábil"
                if any(phrase in task_name.lower() for phrase in fiscal_phrases):
                    tipo_fechamento = "fiscal"
                    
                customers_list = detail.get("customers", [])
                if not customers_list:
                    customers_list = [{"customer": detail.get("customer", {})}]
                
                alertas_enviados = 0
                
                for customer_item in customers_list:
                    customer = customer_item.get("customer", {}) if isinstance(customer_item, dict) else {}
                    customer_id = customer.get("_id")
                    
                    company_department = detail.get("company_department", {}).get("_id")
                    if not company_department:
                        company_department = customer.get("department_id")
                        if not company_department and isinstance(customer_item, dict):
                            company_department = customer_item.get("department_id")
                    
                    if not customer_id or not company_department:
                        logger.warning(f"Cliente ignorado: Não foi possível obter customer_id ou company_department")
                        logger.debug(f"Customer ID: {customer_id}, Company Department: {company_department}")
                        continue
                        
                    logger.info(f"Enviando alerta de documentos incompletos para cliente: {customer.get('name', 'Nome desconhecido')}")
                    resp_comment = send_task_comment(token, task_id, competence=competencia, 
                                                   customer_id=customer_id, company_department=company_department)
                    
                    if "sucesso" in resp_comment.lower():
                        alertas_enviados += 1
                
                estatisticas["alertas_enviados"] += alertas_enviados
                logger.info(f"Total de alertas enviados para esta tarefa: {alertas_enviados}")
                
            else:
                logger.info(f"Tarefa {task_id} não possui documentos. Enviando aviso.")
                estatisticas["tarefas_sem_documentos"] += 1
                
                tipo_fechamento = "contábil"
                if any(phrase in task_name.lower() for phrase in fiscal_phrases):
                    tipo_fechamento = "fiscal"
                    
                from api import send_task_comment
                
                customers_list = detail.get("customers", [])
                if not customers_list:
                    customers_list = [{"customer": detail.get("customer", {})}]
                
                alertas_enviados = 0
                
                for customer_item in customers_list:
                    customer = customer_item.get("customer", {}) if isinstance(customer_item, dict) else {}
                    customer_id = customer.get("_id")
                    
                    company_department = detail.get("company_department", {}).get("_id")
                    if not company_department:
                        company_department = customer.get("department_id")
                        if not company_department and isinstance(customer_item, dict):
                            company_department = customer_item.get("department_id")
                    
                    if not customer_id or not company_department:
                        logger.warning(f"Cliente ignorado: Não foi possível obter customer_id ou company_department")
                        logger.debug(f"Customer ID: {customer_id}, Company Department: {company_department}")
                        continue
                        
                    logger.info(f"Enviando alerta de documentos faltantes para cliente: {customer.get('name', 'Nome desconhecido')}")
                    resp_comment = send_task_comment(token, task_id, competence=competencia, 
                                                   customer_id=customer_id, company_department=company_department)
                    
                    if "sucesso" in resp_comment.lower():
                        alertas_enviados += 1
                
                estatisticas["alertas_enviados"] += alertas_enviados
                logger.info(f"Total de alertas enviados para esta tarefa: {alertas_enviados}")
            
            resultado_status = update_task_status(token, task_id)
            logger.info(f"Resultado da alteração de status: {resultado_status}")
            estatisticas["tarefas_concluidas"] += 1
        
        estatisticas["empresas_processadas"] = len(empresas_com_documentos)
        
        end_processing_time = pytime.time()  # Aqui também
        total_time = end_processing_time - start_processing_time
        estatisticas["tempo_total"] = total_time
        if total_time < 60:
            tempo_total_str = f"{total_time:.2f} seg"
        else:
            tempo_total_str = f"{total_time/60:.2f} min"
        logger.info(f"===== RESUMO DA EXECUÇÃO =====")
        logger.info(f"Tempo Total: {tempo_total_str}")
        logger.info(f"Empresas Carregadas: {estatisticas['empresas_carregadas']}")
        logger.info(f"Empresas com Documentos Processados: {estatisticas['empresas_processadas']}")
        logger.info(f"Usuários Processados: {len(users)}")
        logger.info(f"Tarefas Alertadas: {estatisticas['tarefas_sem_documentos']}")
        logger.info(f"Alertas Enviados: {estatisticas['alertas_enviados']}")
        logger.info(f"Tarefas Processadas com Sucesso: {estatisticas['tarefas_processadas_com_sucesso']}")
        logger.info(f"Documentos Baixados: {estatisticas['documentos_baixados']}")
        # imagem_path = gerar_dashboard_estatisticas(estatisticas)
        # logger.info(f"Dashboard de estatísticas salvo em: {imagem_path}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join("logs", f"execucao_{timestamp}.txt")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"===== LOG DE EXECUÇÃO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n\n")
            f.write(f"Tempo Total: {tempo_total_str}\n")
            f.write(f"Empresas Carregadas: {estatisticas['empresas_carregadas']}\n")
            f.write(f"Empresas com Documentos Processados: {estatisticas['empresas_processadas']}\n")
            f.write(f"Usuários Processados: {len(users)}\n")
            f.write(f"Tarefas Alertadas: {estatisticas['tarefas_sem_documentos']}\n")
            f.write(f"Alertas Enviados: {estatisticas['alertas_enviados']}\n")
            f.write(f"Tarefas Processadas com Sucesso: {estatisticas['tarefas_processadas_com_sucesso']}\n")
            f.write(f"Documentos Baixados: {estatisticas['documentos_baixados']}\n")
        logger.info(f"Log de execução salvo em: {log_path}")
        logger.info("Execução finalizada com sucesso.")
        # Persist a JSON summary so frontend can display it
        summary_path = os.path.join("logs", f"last_run_summary_{timestamp}.json")
        try:
            with open(summary_path, 'w', encoding='utf-8') as sf:
                json.dump(estatisticas, sf, default=str, indent=2)
            logger.info(f"Resumo da execução salvo em: {summary_path}")
        except Exception as e:
            logger.warning(f"Não foi possível salvar resumo da execução: {e}")
        return True
    except Exception as e:
        logger.error(f"Erro durante o processamento: {str(e)}", exc_info=True)
        # write a minimal summary even on error
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_path = os.path.join("logs", f"last_run_summary_{timestamp}.json")
            with open(summary_path, 'w', encoding='utf-8') as sf:
                err_summary = {"error": str(e), "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                json.dump(err_summary, sf, default=str, indent=2)
            logger.info(f"Resumo (erro) salvo em: {summary_path}")
        except Exception:
            logger.debug('Falha ao gravar resumo de erro')
        return False

# The hourly verification function was removed — use realizar_processamento directly.

def programar_verificacoes():
    # Configurar para executar todos os dias às 8:30 com data atual
    schedule.every().day.at("08:30").do(lambda: realizar_processamento(
        start_date=datetime.now().strftime("%Y-%m-%d"),
        end_date=datetime.now().strftime("%Y-%m-%d")
    ))
    
    logger.info("🤖 Sistema iniciado com processamento automático às 08:30 diariamente")
    logger.info("📅 O robô processará tarefas da data atual automaticamente")
    logger.info("⏰ Próxima execução: todos os dias às 08:30")
    
    import sys
    start_date = None
    end_date = None
    
    # Verificar se foram passadas datas via argumentos de linha de comando
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg == "--start-date" and i < len(sys.argv) - 1:
                start_date = sys.argv[i + 1]
            elif arg == "--end-date" and i < len(sys.argv) - 1:
                end_date = sys.argv[i + 1]
    
    # Se foram fornecidas datas, executar com essas datas
    if start_date or end_date:
        logger.info(f"🎯 Executando AGORA com datas personalizadas: {start_date or 'hoje'} até {end_date or start_date or 'hoje'}")
        realizar_processamento(start_date, end_date)
    else:
        # Senão, executar uma vez com a data atual
        current_date = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"🚀 Executando AGORA com data atual: {current_date}")
        realizar_processamento(start_date=current_date, end_date=current_date)
    
    logger.info("⏱️ Aguardando próxima execução programada...")
    
    # Loop principal do scheduler
    while True:
        schedule.run_pending()
        pytime.sleep(60)  # Verificar a cada minuto
