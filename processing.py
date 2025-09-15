# processing.py
import os, sys, json, shutil
import time as pytime  # Renomeie para evitar conflito
from datetime import datetime, date, timedelta, time
import schedule
from logger_config import logger
from config import CONFIG_FILE, DOWNLOAD_BASE_DIR, DEBUG_MODE
from api import (get_token, get_all_companies, get_all_users, search_all_customer_tasks,
                 get_task_detail, process_task_documents, update_task_status)
from dashboard import gerar_dashboard_estatisticas
import subprocess
from file_utils import sanitize_filename, truncate_name, iso_to_mes_ano, safe_move_folder, monta_caminho_contabil, monta_caminho_fiscal
from debug_utils import create_task_debug_folder
import config as config_module

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

        phrases_fiscal = ["envio de documentos fiscais", "envio  de documentos fiscais", "envio do bloco" ,"das notas fiscais de entrada para classificação", "cobrança de documentos fiscais", "envio dos documentos fiscais", "envio do informe de rendimentos financeiros - trimestre", "cobrança do informe de rendimentos financeiros - trimestre", "envio da relação dos recebimentos"]
        phrase_contabil = "cobrança de documentos contábeis"
        filtered_tasks = []
        
        for task in tasks_today:
            name_lower = task.get("name", "").lower()
            if any(phrase in name_lower for phrase in phrases_fiscal) or phrase_contabil in name_lower:
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
                if "fiscal" in task_name.lower():
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
                if "fiscal" in task_name.lower():
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
        imagem_path = gerar_dashboard_estatisticas(estatisticas)
        logger.info(f"Dashboard de estatísticas salvo em: {imagem_path}")
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
        try:
            os.startfile(imagem_path)
        except:
            logger.warning("Não foi possível abrir o dashboard automaticamente.")
        return True
    except Exception as e:
        logger.error(f"Erro durante o processamento: {str(e)}", exc_info=True)
        return False

def executar_verificacao_horaria(start_date=None, end_date=None, force_execution=False):
    """
    Executa uma única verificação de tarefas.
    
    Args:
        start_date (str, optional): Data inicial para busca de tarefas.
        end_date (str, optional): Data final para busca de tarefas.
        force_execution (bool, optional): Parâmetro mantido para compatibilidade, mas não utilizado.
        
    Returns:
        bool: True se a verificação foi realizada com sucesso, False caso contrário.
    """
    logger.info(f"Executando verificação horária.")
    
    try:
        # Removida a verificação de horário (18h)
        
        # Executar o processamento
        processos_ok = realizar_processamento(start_date, end_date)
        
        if processos_ok:
            logger.info("Verificação horária concluída com sucesso.")
        else:
            logger.warning("Verificação horária completou, mas com erros.")
        return processos_ok
    except Exception as e:
        logger.error(f"Erro durante verificação horária: {str(e)}", exc_info=True)
        return False

def programar_verificacoes():
    schedule.every().day.at("05:00").do(executar_verificacao_horaria)
    logger.info("Sistema iniciado com verificação diária configurada.")
    logger.info("Primeira execução iniciando agora...")
    
    import sys
    start_date = None
    end_date = None
    
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg == "--start-date" and i < len(sys.argv) - 1:
                start_date = sys.argv[i + 1]
            elif arg == "--end-date" and i < len(sys.argv) - 1:
                end_date = sys.argv[i + 1]
    
    if start_date or end_date:
        logger.info(f"Executando com datas personalizadas: {start_date or 'hoje'} até {end_date or start_date or 'hoje'}")
        executar_verificacao_horaria(start_date, end_date)
    else:
        executar_verificacao_horaria()
        
    while True:
        schedule.run_pending()
        pytime.sleep(60)  # Aqui mudamos de time.sleep() para pytime.sleep()
