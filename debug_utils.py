import os
import datetime
import re
from logger_config import logger

def create_task_debug_folder(base_dir, task_name, debug_mode=False):
    """
    Cria uma pasta específica para cada tarefa quando em modo debug
    
    Args:
        base_dir (str): Diretório base de downloads
        task_name (str): Nome da tarefa
        debug_mode (bool): Se está em modo debug
        
    Returns:
        str: Caminho para a pasta criada ou o diretório base se não estiver em modo debug
    """
    # Se não estiver em modo debug, retorna apenas o diretório base
    if not debug_mode:
        return base_dir
    
    # Verificar se o diretório base existe
    if not os.path.exists(base_dir):
        try:
            os.makedirs(base_dir, exist_ok=True)
            logger.info(f"Criado diretório base: {base_dir}")
        except Exception as e:
            logger.error(f"Erro ao criar diretório base {base_dir}: {e}")
            return base_dir
    
    # Limpa o nome da tarefa de forma mais robusta
    # Remove caracteres especiais mantendo apenas alfanuméricos, espaços e alguns caracteres seguros
    safe_task_name = re.sub(r'[^\w\s\-]', '_', task_name)
    
    # Remove múltiplos underscores consecutivos
    safe_task_name = re.sub(r'_{2,}', '_', safe_task_name)
    
    # Remove espaços extras no início e fim
    safe_task_name = safe_task_name.strip()
    
    # Limita o tamanho para evitar problemas com caminhos muito longos
    if len(safe_task_name) > 50:
        safe_task_name = safe_task_name[:47] + "..."
        
    # Gera um timestamp único para evitar duplicações
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Cria o nome da pasta combinando o nome da tarefa e o timestamp
    folder_name = f"{safe_task_name}_{timestamp}"
    
    # Caminho completo da pasta
    task_folder_path = os.path.join(base_dir, folder_name)
    
    # Normaliza e usa caminho absoluto para garantir consistência
    task_folder_path = os.path.abspath(os.path.normpath(task_folder_path))
    
    # Cria a pasta se ela não existir
    try:
        if not os.path.exists(task_folder_path):
            os.makedirs(task_folder_path, exist_ok=True)
            logger.info(f"Pasta de debug criada: {task_folder_path}")
    except Exception as e:
        logger.error(f"Falha ao criar diretório: {task_folder_path}. Erro: {str(e)}")
        # Em caso de falha, retornar o diretório base como fallback
        return base_dir
    
    # Verificar permissões de escrita
    if not os.access(task_folder_path, os.W_OK):
        logger.error(f"Pasta criada mas sem permissão de escrita: {task_folder_path}")
        return base_dir
        
    logger.info(f"Usando pasta de debug para tarefa: {task_folder_path}")
    
    return task_folder_path
