# task_inspector.py - Ferramenta para inspecionar detalhes de tarefas do Gestta
import os, json, sys
import time
from datetime import datetime, date, timedelta
from logger_config import logger
from config import CONFIG_FILE
from api import (get_token, get_all_companies, get_all_users, search_all_customer_tasks,
                get_task_detail)

def load_config():
    """Carrega as configurações completas do sistema"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Erro ao carregar configuração: {e}")
        return {}

def search_tasks():
    """Busca tarefas usando a mesma lógica do código principal"""
    config = load_config()
    if not config:
        print("Não foi possível carregar o arquivo de configuração")
        return None, None
    
    email = config.get("credentials", {}).get("email", "")
    password = config.get("credentials", {}).get("password", "")
    selected_companies = config.get("selected_companies", [])
    selected_users = config.get("selected_users", [])
    
    if not email or not password:
        print("Credenciais não encontradas no arquivo de configuração")
        return None, None
    
    token = get_token(email=email, password=password)
    if not token:
        print("Não foi possível obter o token de autenticação")
        return None, None
    
    print("Buscando empresas e usuários...")
    companies = get_all_companies(token, selected_companies)
    users = get_all_users(token, selected_users)
    
    if not companies or not users:
        print("Nenhuma empresa ou usuário encontrado nas configurações")
        return None, None
    
    company_ids = [c["_id"] for c in companies if "_id" in c]
    user_ids = [u["_id"] for u in users if "_id" in u]
    
    # Definir período de busca
    print("\nEscolha o período para busca de tarefas:")
    print("1. Tarefas com vencimento em 6 dias (padrão para alertas)")
    print("2. Tarefas vencendo entre -9 e -2 dias (padrão para download)")
    print("3. Tarefas com outra data específica")
    print("4. Tarefas de hoje")
    
    option = input("Selecione uma opção (1-4): ")
    
    if option == "1":
        # 6 dias para frente (padrão para alertas)
        alert_date = date.today() + timedelta(days=6)
        start_date_str = alert_date.strftime("%Y-%m-%d") + "T00:00:00-03:00"
        end_date_str = alert_date.strftime("%Y-%m-%d") + "T23:59:59-03:00"
        print(f"Buscando tarefas com vencimento em: {alert_date.strftime('%d/%m/%Y')}")
    
    elif option == "2":
        # -9 a -2 dias (padrão para download)
        start_date = date.today() - timedelta(days=9)
        end_date = date.today() - timedelta(days=2)
        start_date_str = start_date.strftime("%Y-%m-%d") + "T00:00:00-03:00"
        end_date_str = end_date.strftime("%Y-%m-%d") + "T23:59:59-03:00"
        print(f"Buscando tarefas com vencimento entre: {start_date.strftime('%d/%m/%Y')} e {end_date.strftime('%d/%m/%Y')}")
    
    elif option == "3":
        # Data personalizada
        try:
            date_input = input("Informe a data (DD/MM/AAAA): ")
            custom_date = datetime.strptime(date_input, "%d/%m/%Y").date()
            start_date_str = custom_date.strftime("%Y-%m-%d") + "T00:00:00-03:00"
            end_date_str = custom_date.strftime("%Y-%m-%d") + "T23:59:59-03:00"
            print(f"Buscando tarefas com vencimento em: {custom_date.strftime('%d/%m/%Y')}")
        except ValueError:
            print("Formato de data inválido. Usando data de hoje.")
            today = date.today()
            start_date_str = today.strftime("%Y-%m-%d") + "T00:00:00-03:00"
            end_date_str = today.strftime("%Y-%m-%d") + "T23:59:59-03:00"
    
    else:
        # Opção padrão: hoje
        today = date.today()
        start_date_str = today.strftime("%Y-%m-%d") + "T00:00:00-03:00"
        end_date_str = today.strftime("%Y-%m-%d") + "T23:59:59-03:00"
        print(f"Buscando tarefas com vencimento para hoje: {today.strftime('%d/%m/%Y')}")
    
    print("\nBuscando tarefas, aguarde...")
    tasks = search_all_customer_tasks(token, company_ids, user_ids, start_date_str, end_date_str)
    
    if not tasks:
        print("Nenhuma tarefa encontrada no período especificado.")
        return None, None
    
    # Mostrar resultados iniciais
    print(f"\nForam encontradas {len(tasks)} tarefas no período.")
    
    # Perguntar se quer filtrar
    filter_option = input("\nDeseja filtrar por tipo de tarefa? (s/n): ").lower()
    
    if filter_option == 's':
        print("\nTipos de filtro disponíveis:")
        print("1. Cobrança de documentos fiscais")
        print("2. Cobrança de documentos contábeis")
        print("3. Qualquer tarefa de cobrança de documentos")
        print("4. Digite um texto personalizado para filtrar")
        
        filter_choice = input("Selecione uma opção (1-4): ")
        
        if filter_choice == "1":
            filter_phrase = "envio de documentos fiscais"
        elif filter_choice == "2":
            filter_phrase = "cobrança de documentos contábeis"
        elif filter_choice == "3":
            filter_phrase = "cobrança de documentos"
        elif filter_choice == "4":
            filter_phrase = input("Digite o texto para filtrar: ").lower()
        else:
            filter_phrase = "cobrança de documentos"
        
        # Aplicar filtro
        filtered_tasks = []
        for task in tasks:
            name_lower = task.get("name", "").lower()
            if filter_phrase in name_lower:
                filtered_tasks.append(task)
        
        print(f"\nForam encontradas {len(filtered_tasks)} tarefas após filtro.")
        tasks = filtered_tasks
    
    return token, tasks

def inspect_task(token, task_id):
    """Inspeciona uma tarefa específica e mostra seus detalhes"""
    task_detail = get_task_detail(token, task_id)
    if not task_detail:
        print(f"Não foi possível obter detalhes da tarefa {task_id}")
        return
    
    print("\n" + "="*50)
    print("DETALHES DA TAREFA")
    print("="*50)
    
    # Informações básicas
    print(f"ID: {task_detail.get('_id')}")
    print(f"Nome: {task_detail.get('name')}")
    print(f"Status: {task_detail.get('status')}")
    
    # Data de vencimento
    due_date = task_detail.get('due_date')
    if due_date:
        try:
            dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            print(f"Data de Vencimento: {dt.strftime('%d/%m/%Y')}")
        except:
            print(f"Data de Vencimento: {due_date}")
    
    # Informações da empresa
    customer = task_detail.get('customer', {})
    print("\n--- EMPRESA ---")
    print(f"ID: {customer.get('_id')}")
    print(f"Nome: {customer.get('name')}")
    print(f"Código: {customer.get('code')}")
    
    # Informações do responsável
    print("\n--- RESPONSÁVEL ---")
    
    # Responsável principal
    company_user = task_detail.get('company_user', {})
    print(f"ID: {company_user.get('_id')}")
    print(f"Nome: {company_user.get('name')}")
    print(f"Email: {company_user.get('email')}")
    
    # Responsáveis adicionais
    print("\n--- RESPONSÁVEIS ADICIONAIS ---")
    assigned_users = task_detail.get('assigned_users', [])
    if assigned_users:
        for i, user in enumerate(assigned_users, 1):
            print(f"{i}. Nome: {user.get('name')}")
            print(f"   Email: {user.get('email')}")
            print(f"   ID: {user.get('_id')}")
    else:
        print("Nenhum responsável adicional")
    
    # Documentos
    print("\n--- DOCUMENTAÇÃO SOLICITADA ---")
    doc_req = task_detail.get('document_request', {})
    req_docs = doc_req.get('requested_documents', [])
    if req_docs:
        for i, doc in enumerate(req_docs, 1):
            print(f"{i}. {doc.get('name')}")
            files = doc.get('files', [])
            if files:
                print(f"   {len(files)} arquivo(s)")
                for j, file in enumerate(files[:5], 1):
                    print(f"   - {file.get('file_name')} ({file.get('_id')})")
                if len(files) > 5:
                    print(f"   ... mais {len(files) - 5} arquivo(s) não exibidos")
            else:
                print("   Nenhum arquivo")
    else:
        print("Nenhum documento solicitado")
    
    # Salvar objeto completo em um arquivo JSON para referência
    details_file = f"task_{task_id}_details.json"
    with open(details_file, "w", encoding="utf-8") as f:
        json.dump(task_detail, f, indent=2, ensure_ascii=False)
    
    print(f"\nObjeto completo da tarefa salvo em: {details_file}")
    print("="*50)

def show_task_structure(token, task_id):
    """Mostra a estrutura completa do objeto da tarefa para referência"""
    task_detail = get_task_detail(token, task_id)
    if not task_detail:
        print(f"Não foi possível obter detalhes da tarefa {task_id}")
        return
    
    def print_structure(obj, prefix="", is_last=True, skip_content=True):
        """Função recursiva para mostrar a estrutura do objeto"""
        if isinstance(obj, dict):
            for i, (key, value) in enumerate(obj.items()):
                is_last_item = i == len(obj) - 1
                if isinstance(value, (dict, list)) and len(value) > 0:
                    print(f"{prefix}{'└── ' if is_last else '├── '}{key}: {type(value).__name__}")
                    new_prefix = prefix + ('    ' if is_last else '│   ')
                    print_structure(value, new_prefix, is_last_item, skip_content)
                else:
                    content = str(value)
                    if skip_content and len(content) > 30:
                        content = content[:27] + "..."
                    print(f"{prefix}{'└── ' if is_last_item else '├── '}{key}: {content}")
        elif isinstance(obj, list) and len(obj) > 0:
            for i, item in enumerate(obj[:min(3, len(obj))]):
                is_last_item = i == min(2, len(obj) - 1)
                if isinstance(item, (dict, list)):
                    print(f"{prefix}{'└── ' if is_last_item and i == len(obj) - 1 or len(obj) <= 3 else '├── '}[{i}]: {type(item).__name__}")
                    new_prefix = prefix + ('    ' if is_last_item and i == len(obj) - 1 or len(obj) <= 3 else '│   ')
                    print_structure(item, new_prefix, is_last_item, skip_content)
                else:
                    content = str(item)
                    if skip_content and len(content) > 30:
                        content = content[:27] + "..."
                    print(f"{prefix}{'└── ' if is_last_item and i == len(obj) - 1 or len(obj) <= 3 else '├── '}[{i}]: {content}")
            if len(obj) > 3:
                print(f"{prefix}└── ... mais {len(obj) - 3} item(s)")
    
    print("\n" + "="*50)
    print(f"ESTRUTURA DO OBJETO DA TAREFA (ID: {task_id})")
    print("="*50)
    print_structure(task_detail)
    print("="*50)

def display_task_list(tasks):
    """Exibe uma lista de tarefas formatada para seleção"""
    print("\n" + "="*80)
    print(f"{'ID':4} | {'EMPRESA':30} | {'NOME DA TAREFA':40}")
    print("="*80)
    
    for i, task in enumerate(tasks, 1):
        task_name = task.get('name', '')[:40]
        company_name = task.get('customer', {}).get('name', '')[:30]
        print(f"{i:4} | {company_name:30} | {task_name:40}")
    
    print("="*80)

if __name__ == "__main__":
    # Verificar se foi fornecido um ID de tarefa específico
    if len(sys.argv) > 1:
        # Modo antigo: usar ID fornecido
        task_id = sys.argv[1]
        show_structure = "--structure" in sys.argv
        
        # Carregar credenciais e obter token
        config = load_config()
        email = config.get("credentials", {}).get("email", "")
        password = config.get("credentials", {}).get("password", "")
        token = get_token(email=email, password=password)
        
        if not token:
            print("Não foi possível obter token de autenticação")
            sys.exit(1)
            
        if show_structure:
            show_task_structure(token, task_id)
        else:
            inspect_task(token, task_id)
    else:
        # Novo modo: buscar tarefas primeiro
        token, tasks = search_tasks()
        
        if not token or not tasks:
            print("Não foi possível encontrar tarefas ou obter token")
            print("Uso alternativo: python task_inspector.py <task_id> [--structure]")
            sys.exit(1)
        
        # Exibir lista de tarefas
        display_task_list(tasks)
        
        # Usuário seleciona uma tarefa
        while True:
            selection = input("\nDigite o número da tarefa para inspecionar (ou 'q' para sair): ")
            if selection.lower() == 'q':
                break
                
            try:
                index = int(selection) - 1
                if 0 <= index < len(tasks):
                    selected_task = tasks[index]
                    task_id = selected_task.get("_id")
                    
                    # Perguntar se quer estrutura ou detalhes
                    view_type = input("Ver estrutura completa? (s/n): ").lower()
                    if view_type == 's':
                        show_task_structure(token, task_id)
                    else:
                        inspect_task(token, task_id)
                else:
                    print(f"Número inválido. Escolha entre 1 e {len(tasks)}")
            except ValueError:
                print("Por favor, digite um número válido")
