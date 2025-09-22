# file_utils.py
import os, re, time, zipfile, shutil, subprocess
from datetime import datetime
import config  # Import the entire config module to access its variables
from logger_config import logger

def sanitize_filename(filename):
    """
    Sanitiza um nome de arquivo removendo caracteres inválidos.
    Também remove espaços extra no início e fim.
    """
    # Substituir caracteres não permitidos em sistemas de arquivos
    invalid_chars = r'[\/*?:"<>|]'
    clean_name = re.sub(invalid_chars, "_", filename)
    
    # Remover caracteres de controle
    clean_name = re.sub(r'[\x00-\x1f\x7f]', '', clean_name)
    
    # Substituir múltiplos espaços por um único espaço
    clean_name = re.sub(r'\s+', ' ', clean_name)
    
    # Remover espaços no início e fim de forma agressiva
    clean_name = clean_name.strip()
    
    # Garantir que o nome não termine com espaço ou ponto
    clean_name = clean_name.rstrip('. ')
    
    # Adicionar verificação extra para remover qualquer espaço no final
    while clean_name.endswith(" "):
        clean_name = clean_name[:-1]
    
    # Se o nome estiver vazio após limpeza, usar um nome padrão
    if not clean_name:
        clean_name = "arquivo"
        
    return clean_name

def create_safe_path(base_dir, name, prefix=""):
    """
    Cria um caminho de diretório seguro para salvar arquivos.
    """
    base_dir = base_dir.strip()
    safe_name = re.sub(r'[^\w\-]', '_', name)
    
    if len(safe_name) > 30:
        safe_name = safe_name[:27] + "..."
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if prefix:
        dir_name = f"{prefix}_{safe_name}_{timestamp}"
    else:
        dir_name = f"{safe_name}_{timestamp}"
    
    full_path = os.path.normpath(os.path.join(base_dir, dir_name))
    
    return full_path

def truncate_name(name, max_length=100):
    return name if len(name) <= max_length else name[:max_length]

def iso_to_mes_ano(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return (f"{dt.month:02d}", str(dt.year))
    except Exception:
        return ("00", "0000")

def format_date_only(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return "Não disponível"

def remove_if_empty(folder):
    if os.path.exists(folder) and os.path.isdir(folder):
        if not os.listdir(folder):
            os.rmdir(folder)
            return True
    return False

def is_tool_installed(name):
    """Verifica se uma ferramenta de linha de comando está no PATH."""
    return shutil.which(name) is not None

def extract_archive(archive_path, destination_folder):
    """
    Extrai um arquivo compactado usando a ferramenta apropriada baseada na extensão.
    Suporta .zip, .rar, e .7z.
    """
    if not os.path.exists(archive_path):
        logger.error(f"Arquivo compactado não encontrado: {archive_path}")
        return False

    file_ext = os.path.splitext(archive_path)[1].lower()
    os.makedirs(destination_folder, exist_ok=True)
    cmd = []

    if file_ext == '.zip':
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(destination_folder)
            logger.info(f"Arquivo ZIP extraído com sucesso: {archive_path}")
            os.remove(archive_path)
            return True
        except zipfile.BadZipFile:
            logger.error(f"Arquivo ZIP corrompido: {archive_path}")
            return False
        except Exception as e:
            logger.error(f"Erro ao extrair ZIP {archive_path}: {e}")
            return False

    elif file_ext == '.rar':
        if is_tool_installed("unrar"):
            cmd = ["unrar", "x", "-o+", "-y", archive_path, destination_folder]
        else:
            logger.error(f"Comando 'unrar' não encontrado. Instale o pacote 'unrar' para extrair arquivos .rar.")
            return False

    elif file_ext == '.7z':
        if is_tool_installed("7z"):
            cmd = ["7z", "x", archive_path, f"-o{destination_folder}", "-y"]
        else:
            logger.error(f"Comando '7z' não encontrado. Instale o pacote 'p7zip-full' para extrair arquivos .7z.")
            return False
    else:
        logger.warning(f"Formato de arquivo não suportado para extração: {file_ext}")
        return False

    try:
        logger.info(f"Extraindo com comando: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            logger.info(f"Arquivo extraído com sucesso: {archive_path}")
            os.remove(archive_path)
            return True
        else:
            logger.error(f"Erro ao extrair {archive_path}. Código: {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
            logger.error(f"Stdout: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout ao extrair {archive_path} - processo cancelado após 5 minutos.")
        return False
    except Exception as e:
        logger.error(f"Erro desconhecido ao extrair {archive_path}: {e}")
        return False

def extract_all_archives(folder_path, recursion_level=0, max_recursion=20):
    """
    Extrai recursivamente todos os arquivos compactados em uma pasta.
    """
    if recursion_level >= max_recursion:
        logger.warning(f"Extração recursiva interrompida no nível {max_recursion}.")
        return 0

    supported_extensions = [".zip", ".rar", ".7z"]
    extracted_count = 0
    
    logger.info(f"Iniciando extração recursiva no nível {recursion_level}: {folder_path}")
    
    # Usar uma lista de arquivos para iterar, pois a extração pode criar novos arquivos
    files_to_process = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            files_to_process.append(os.path.join(root, file))

    for file_path in files_to_process:
        file_lower = file_path.lower()
        if any(file_lower.endswith(ext) for ext in supported_extensions):
            file_name_no_ext = os.path.splitext(os.path.basename(file_path))[0]
            extract_dir = os.path.join(os.path.dirname(file_path), file_name_no_ext)
            
            if extract_archive(file_path, extract_dir):
                extracted_count += 1
                # Chama recursivamente para a nova pasta extraída
                extract_all_archives(extract_dir, recursion_level + 1, max_recursion)

    if extracted_count > 0:
        logger.info(f"Extração recursiva encontrou e processou {extracted_count} arquivos no nível {recursion_level}.")
    
    return extracted_count

def count_files_in_folder(folder):
    """
    Conta arquivos em uma pasta, com informações mais detalhadas para depuração.
    """
    if not os.path.exists(folder) or not os.path.isdir(folder):
        logger.warning(f"Pasta não existe para contagem: {folder}")
        return 0
        
    total_files = 0
    file_extensions = {}
    try:
        for root, _, files in os.walk(folder):
            valid_files = [f for f in files if not f.startswith('.') and not f.startswith('~$')]
            total_files += len(valid_files)
            
            for file in valid_files:
                ext = os.path.splitext(file.lower())[1]
                if not ext:
                    ext = "(sem extensão)"
                file_extensions[ext] = file_extensions.get(ext, 0) + 1
        
        if total_files > 1000:
            logger.info(f"Contagem alta de arquivos em {folder}: {total_files} arquivos")
            logger.info(f"Distribuição por tipo: {file_extensions}")
            
        return total_files
    except Exception as e:
        logger.error(f"Erro ao contar arquivos em {folder}: {e}")
        return 0

def safe_move_folder(src_folder, dest_folder, is_debug_mode=False):
    """
    Move arquivos de uma pasta para outra, lidando com erros de acesso.
    """
    try:
        if not os.path.exists(src_folder):
            return 0
            
        total_files = count_files_in_folder(src_folder)
        
        if is_debug_mode:
            logger.info(f"[DEBUG] Simulando movimentação de {total_files} arquivos de {src_folder} para {dest_folder}")
            return total_files
            
        logger.info(f"Movendo {total_files} arquivos de {src_folder} para {dest_folder}")
        
        try:
            # Usar copytree e depois rmtree é mais robusto que mover arquivo por arquivo
            shutil.copytree(src_folder, dest_folder, dirs_exist_ok=True)
            shutil.rmtree(src_folder)
            logger.info(f"Pasta movida com sucesso: {src_folder} -> {dest_folder}")
        except Exception as e:
            logger.error(f"Erro ao mover pasta {src_folder} para {dest_folder}: {e}")
            # Retorna o número de arquivos que falharam em ser movidos
            return count_files_in_folder(src_folder)
            
        return total_files
    except Exception as e:
        logger.error(f"Erro em safe_move_folder: {e}")
        return 0

def monta_caminho_contabil(customer_code, mes_ano_tuple):
    try:
        base = "/home/roboestatistica/rede/Acesso Digital"
        # A busca da pasta da empresa pode falhar se a rede não estiver montada.
        # Adicionar tratamento de erro para isso.
        if not os.path.exists(base):
            logger.error(f"Caminho base da rede não encontrado: {base}")
            return None
        
        empresa_dir_name = next((p for p in os.listdir(base) if p.startswith(str(customer_code))), None)
        if not empresa_dir_name:
            logger.warning(f"Pasta com código {customer_code} não encontrada em {base}.")
            return None
            
        mes, ano = mes_ano_tuple
        destino = os.path.join(
            base, empresa_dir_name, "02 - Contábil", ano,
            "01 - Fechamento Contábil", mes, "01 - Documentos do cliente"
        )
        return destino
    except Exception as e:
        logger.error(f"Erro em monta_caminho_contabil: {e}")
        return None

def monta_caminho_fiscal(customer_code, mes_ano_tuple):
    try:
        base = "/home/roboestatistica/rede/Acesso Digital"
        if not os.path.exists(base):
            logger.error(f"Caminho base da rede não encontrado: {base}")
            return None

        empresa_dir_name = next((p for p in os.listdir(base) if p.startswith(str(customer_code))), None)
        if not empresa_dir_name:
            logger.warning(f"Pasta com código {customer_code} não encontrada em {base}.")
            return None
            
        mes, ano = mes_ano_tuple
        destino = os.path.join(
            base, empresa_dir_name, "01 - Fiscal", ano,
            "90 - Triagem de Documentos Mensal", mes, "10 - Backup (Winrar)"
        )
        return destino
    except Exception as e:
        logger.error(f"Erro em monta_caminho_fiscal: {e}")
        return None