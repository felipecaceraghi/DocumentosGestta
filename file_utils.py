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
    invalid_chars = r'[\\/*?:"<>|]'
    clean_name = re.sub(invalid_chars, "_", filename)
    
    # Remover caracteres de controle
    clean_name = re.sub(r'[\x00-\x1f\x7f]', '', clean_name)
    
    # Substituir múltiplos espaços por um único espaço
    clean_name = re.sub(r'\s+', ' ', clean_name)
    
    # Remover espaços no início e fim de forma agressiva
    clean_name = clean_name.strip()
    
    # Garantir que o nome não termine com espaço ou ponto (problemático em Windows)
    clean_name = clean_name.rstrip('. ')
    
    # Adicionar verificação extra para remover qualquer espaço no final
    while clean_name.endswith(" "):
        clean_name = clean_name[:-1]
    
    # Se o nome estiver vazio após limpeza, usar um nome padrão
    if not clean_name:
        clean_name = "arquivo"
        
    return clean_name

# Adicionar uma nova função para criar caminhos seguros
def create_safe_path(base_dir, name, prefix=""):
    """
    Cria um caminho de diretório seguro para salvar arquivos, evitando problemas com caracteres especiais.
    
    Args:
        base_dir (str): Diretório base
        name (str): Nome da entidade (tarefa, cliente, etc.)
        prefix (str): Prefixo opcional para o nome do diretório
        
    Returns:
        str: Caminho seguro para uso
    """
    # Remover espaços no início e final
    base_dir = base_dir.strip()
    
    # Sanitizar o nome removendo caracteres problemáticos
    safe_name = re.sub(r'[^\w\-]', '_', name)
    
    # Limitar o tamanho para evitar problemas com caminhos muito longos
    if len(safe_name) > 30:
        safe_name = safe_name[:27] + "..."
    
    # Adicionar timestamp para evitar conflitos
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Construir o nome do diretório com prefixo se fornecido
    if prefix:
        dir_name = f"{prefix}_{safe_name}_{timestamp}"
    else:
        dir_name = f"{safe_name}_{timestamp}"
    
    # Criar o caminho completo e normalizar
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

def find_winrar_executable():
    # Access global variables through the config module
    if config.WINRAR_SEARCH_COMPLETED:
        return config.WINRAR_PATH
    logger.info("Buscando executável do WinRAR no sistema...")
    winrar_executables = ["WinRAR.exe", "UnRAR.exe", "Rar.exe"]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WinRAR") as key:
            path_value = None
            try:
                path_value = winreg.QueryValueEx(key, "exe64")[0]
            except FileNotFoundError:
                try:
                    path_value = winreg.QueryValueEx(key, "exe32")[0]
                except FileNotFoundError:
                    pass
            if not path_value:
                try:
                    path_value = winreg.QueryValueEx(key, "Path")[0]
                    if path_value and os.path.exists(path_value):
                        for exec_name in winrar_executables:
                            full_path = os.path.join(path_value, exec_name)
                            if os.path.exists(full_path):
                                config.WINRAR_PATH = full_path
                                logger.info(f"WinRAR encontrado no registro: {config.WINRAR_PATH}")
                                config.WINRAR_SEARCH_COMPLETED = True
                                return config.WINRAR_PATH
                except FileNotFoundError:
                    pass
            if path_value and os.path.exists(path_value):
                config.WINRAR_PATH = path_value
                logger.info(f"WinRAR encontrado no registro: {config.WINRAR_PATH}")
                config.WINRAR_SEARCH_COMPLETED = True
                return config.WINRAR_PATH
    except Exception as e:
        logger.info(f"Registro do Windows não acessível: {e}")
    common_paths = []
    program_dirs = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    ]
    for prog_dir in program_dirs:
        if os.path.exists(prog_dir):
            for exec_name in winrar_executables:
                common_paths.append(os.path.join(prog_dir, "WinRAR", exec_name))
    for path in common_paths:
        if os.path.exists(path):
            config.WINRAR_PATH = path
            logger.info(f"WinRAR encontrado em caminho comum: {config.WINRAR_PATH}")
            config.WINRAR_SEARCH_COMPLETED = True
            return config.WINRAR_PATH
    logger.info("WinRAR não encontrado em caminhos comuns. Buscando em Program Files...")
    for program_dir in program_dirs:
        if os.path.exists(program_dir):
            for root, dirs, files in os.walk(program_dir):
                if root.count(os.sep) - program_dir.count(os.sep) > 3:
                    continue
                for file in files:
                    if file.lower() in [exe.lower() for exe in winrar_executables]:
                        config.WINRAR_PATH = os.path.join(root, file)
                        logger.info(f"WinRAR encontrado em: {config.WINRAR_PATH}")
                        config.WINRAR_SEARCH_COMPLETED = True
                        return config.WINRAR_PATH
    logger.info("Iniciando busca limitada no drive do sistema...")
    system_drive = os.environ.get("SystemDrive", "C:")
    excluded_dirs = [
        os.path.join(system_drive, "Windows"),
        os.path.join(system_drive, "Windows.old"),
        os.path.join(system_drive, "Users", "All Users"),
        os.path.join(system_drive, "ProgramData"),
        os.path.join(system_drive, "$Recycle.Bin")
    ]
    search_start_time = time.time()
    max_search_time = 60
    for root, dirs, files in os.walk(system_drive):
        if time.time() - search_start_time > max_search_time:
            logger.warning(f"Busca do WinRAR interrompida após {max_search_time} segundos.")
            break
        dirs[:] = [d for d in dirs if os.path.join(root, d) not in excluded_dirs]
        if root.count(os.sep) - system_drive.count(os.sep) > 4:
            dirs[:] = []
            continue
        for file in files:
            if file.lower() in [exe.lower() for exe in winrar_executables]:
                config.WINRAR_PATH = os.path.join(root, file)
                logger.info(f"WinRAR encontrado em: {config.WINRAR_PATH}")
                config.WINRAR_SEARCH_COMPLETED = True
                return config.WINRAR_PATH
    logger.warning("WinRAR não encontrado no sistema após busca limitada.")
    config.WINRAR_SEARCH_COMPLETED = True
    return None

def extract_zip(zip_file_path, destination_folder, remove_original=True, max_filename_length=100):
    """
    Extrai um arquivo ZIP para um diretório de destino, com tratamento para nomes longos.
    
    Args:
        zip_file_path (str): Caminho para o arquivo ZIP
        destination_folder (str): Pasta onde os arquivos serão extraídos
        remove_original (bool): Se True, remove o arquivo ZIP original após extração
        max_filename_length (int): Tamanho máximo permitido para nomes de arquivos
        
    Returns:
        bool: True se a extração for bem-sucedida, False caso contrário
    """
    import zipfile
    import shutil
    import os
    
    if not os.path.exists(zip_file_path):
        logger.error(f"Arquivo ZIP não encontrado: {zip_file_path}")
        return False
    
    try:
        # Garantir que a pasta de destino exista
        os.makedirs(destination_folder, exist_ok=True)
        
        # Contadores para relatório
        renamed_count = 0
        
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            # Lista todos os arquivos no ZIP
            file_list = zip_ref.namelist()
            logger.info(f"ZIP contém {len(file_list)} arquivos")
            
            for file_name in file_list:
                # Verificar se o nome é muito longo
                if len(file_name) > max_filename_length:
                    # Separar caminho do arquivo e nome do arquivo
                    dir_path, full_filename = os.path.split(file_name)
                    filename, extension = os.path.splitext(full_filename)
                    
                    # Truncar o nome mantendo a extensão (removendo 20 caracteres)
                    new_filename = filename[:-20] + extension
                    new_file_path = os.path.join(dir_path, new_filename) if dir_path else new_filename
                    
                    logger.info(f"Renomeando arquivo longo: {file_name} -> {new_file_path}")
                    
                    # Preparar o caminho de destino
                    dest_path = os.path.join(destination_folder, new_file_path)
                    os.makedirs(os.path.dirname(dest_path) if os.path.dirname(dest_path) else destination_folder, exist_ok=True)
                    
                    # Extrair com o novo nome
                    source = zip_ref.open(file_name)
                    with open(dest_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                    source.close()
                    
                    renamed_count += 1
                else:
                    # Para nomes normais, extrair diretamente usando o método extract do zipfile
                    zip_ref.extract(file_name, destination_folder)
        
        if renamed_count > 0:
            logger.info(f"Extração concluída: {renamed_count} arquivos foram renomeados por terem nomes muito longos")
        
        # Remover o arquivo original se solicitado
        if remove_original and os.path.exists(zip_file_path):
            os.remove(zip_file_path)
            logger.info(f"Arquivo ZIP original removido: {zip_file_path}")
        
        return True
            
    except zipfile.BadZipFile:
        logger.error(f"Arquivo ZIP corrompido: {zip_file_path}")
        return False
    except Exception as e:
        logger.error(f"Erro ao extrair ZIP {zip_file_path}: {str(e)}")
        return False

def extract_with_winrar(archive_path, destination_folder):
    if not config.WINRAR_PATH:  # Access through config
        config.WINRAR_PATH = find_winrar_executable()
    if not config.WINRAR_PATH:
        logger.error(f"WinRAR não encontrado. Impossível extrair: {archive_path}")
        return False
    try:
        os.makedirs(destination_folder, exist_ok=True)
        exe_name = os.path.basename(config.WINRAR_PATH).lower()
        if "unrar" in exe_name:
            cmd = [config.WINRAR_PATH, "x", "-o+", "-y", archive_path, f"{destination_folder}\\"]
        elif "rar" in exe_name:
            cmd = [config.WINRAR_PATH, "x", "-o+", "-y", archive_path, f"{destination_folder}\\"]
        else:
            cmd = [config.WINRAR_PATH, "x", "-ibck", archive_path, f"{destination_folder}\\", "-o+", "-y"]
        logger.info(f"Extraindo com WinRAR: {archive_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode <= 1:
            logger.info(f"Arquivo extraído com sucesso: {archive_path}")
            os.remove(archive_path)
            return True
        else:
            logger.error(f"Erro {result.returncode} ao extrair {archive_path}.")
            logger.error(f"Mensagem: {result.stderr or result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout ao extrair {archive_path} - processo cancelado após 5 minutos.")
        return False
    except Exception as e:
        logger.error(f"Erro desconhecido ao extrair {archive_path}: {str(e)}")
        return False

def extract_all_archives(folder_path, recursion_level=0, max_recursion=20):
    """
    Extrai recursivamente todos os arquivos compactados em uma pasta.
    
    Args:
        folder_path (str): Caminho da pasta a ser processada
        recursion_level (int): Nível atual de recursão
        max_recursion (int): Nível máximo de recursão permitido
        
    Returns:
        int: Número de arquivos compactados extraídos
    """
    winrar_extensions = [".rar", ".7z", ".arj", ".cab", ".lzh", ".tar", ".gz", ".bz2", ".xz"]
    if not config.WINRAR_PATH:
        config.WINRAR_PATH = find_winrar_executable()
    has_winrar = bool(config.WINRAR_PATH)
    if not has_winrar:
        logger.warning("WinRAR não encontrado! Apenas arquivos ZIP serão extraídos.")
    if recursion_level >= max_recursion:
        logger.warning(f"Extração recursiva interrompida após atingir o limite de {max_recursion} níveis.")
        return 0
    extracted_count = 0
    logger.info(f"Iniciando extração recursiva no nível {recursion_level}: {folder_path}")
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_lower = file.lower()
            file_name_no_ext = os.path.splitext(file)[0]
            extract_dir = os.path.join(root, file_name_no_ext)
            if file_lower.endswith(".zip"):
                if extract_zip(file_path, extract_dir):
                    extracted_count += 1
            elif has_winrar and any(file_lower.endswith(ext) for ext in winrar_extensions):
                if extract_with_winrar(file_path, extract_dir):
                    extracted_count += 1
    if extracted_count > 0:
        logger.info(f"Extração recursiva encontrou {extracted_count} arquivos compactados no nível {recursion_level}.")
        extract_all_archives(folder_path, recursion_level + 1, max_recursion)
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
            # Conta apenas arquivos que não são temporários ou de sistema
            valid_files = [f for f in files if not f.startswith('.') and not f.startswith('~$')]
            total_files += len(valid_files)
            
            # Conta extensões para depuração
            for file in valid_files:
                ext = os.path.splitext(file.lower())[1]
                if not ext:
                    ext = "(sem extensão)"
                file_extensions[ext] = file_extensions.get(ext, 0) + 1
        
        # Exibe estatísticas para verificar se a contagem parece correta
        if total_files > 1000:  # Apenas para contagens grandes
            logger.info(f"Contagem alta de arquivos em {folder}: {total_files} arquivos")
            logger.info(f"Distribuição por tipo: {file_extensions}")
            
        return total_files
    except Exception as e:
        logger.error(f"Erro ao contar arquivos em {folder}: {e}")
        return 0

def safe_move_folder(src_folder, dest_folder, is_debug_mode=False):
    """
    Move arquivos de uma pasta para outra, lidando com erros de acesso.
    Em modo debug, apenas registra o que seria feito sem executar a movimentação.
    
    Args:
        src_folder (str): Pasta de origem
        dest_folder (str): Pasta de destino
        is_debug_mode (bool): Se está em modo debug
        
    Returns:
        int: Número de arquivos processados
    """
    try:
        if not os.path.exists(src_folder):
            return 0
            
        total_files = count_files_in_folder(src_folder)
        
        # Em modo debug, apenas registra e não move arquivos
        if is_debug_mode:
            logger.info(f"[DEBUG] Simulando movimentação de arquivos (sem mover): {src_folder} -> {dest_folder}")
            logger.info(f"[DEBUG] Total de {total_files} arquivos seriam movidos se não estivesse em modo DEBUG")
            return total_files
            
        # Código de movimentação real apenas executado quando NÃO está em debug mode
        logger.info(f"Movendo {total_files} arquivos de {src_folder} para {dest_folder}")
        
        try:
            if os.path.exists(dest_folder):
                # Se a pasta de destino já existe, copiar arquivo por arquivo
                for root, dirs, files in os.walk(src_folder):
                    for file in files:
                        src_file = os.path.join(root, file)
                        # Calcular o caminho relativo para manter a estrutura
                        rel_path = os.path.relpath(root, src_folder)
                        if rel_path == '.':
                            dest_dir = dest_folder
                        else:
                            dest_dir = os.path.join(dest_folder, rel_path)
                        os.makedirs(dest_dir, exist_ok=True)
                        dest_file = os.path.join(dest_dir, file)
                        try:
                            shutil.copy2(src_file, dest_file)
                            logger.debug(f"Copiado: {src_file} -> {dest_file}")
                        except Exception as e:
                            logger.error(f"Erro ao copiar arquivo {src_file}: {e}")
            else:
                # Se a pasta destino não existe, tentar mover a pasta inteira
                try:
                    shutil.copytree(src_folder, dest_folder)
                    logger.info(f"Pasta copiada: {src_folder} -> {dest_folder}")
                except (PermissionError, OSError) as e:
                    logger.error(f"Erro ao copiar pasta: {e}")
                    # Se falhar, tentar copiar arquivo por arquivo
                    for root, dirs, files in os.walk(src_folder):
                        for file in files:
                            src_file = os.path.join(root, file)
                            rel_path = os.path.relpath(root, src_folder)
                            if rel_path == '.':
                                dest_dir = dest_folder
                            else:
                                dest_dir = os.path.join(dest_folder, rel_path)
                            os.makedirs(dest_dir, exist_ok=True)
                            dest_file = os.path.join(dest_dir, file)
                            try:
                                shutil.copy2(src_file, dest_file)
                            except Exception as e:
                                logger.error(f"Erro ao copiar arquivo {src_file}: {e}")
            
            # Remover a pasta original após copiar
            try:
                shutil.rmtree(src_folder)
            except Exception as e:
                logger.error(f"Erro ao remover pasta original {src_folder}: {e}")
                    
        except Exception as e:
            logger.error(f"Erro ao mover pasta {src_folder} para {dest_folder}: {e}")
            return count_files_in_folder(src_folder)
            
        return total_files
    except Exception as e:
        logger.error(f"Erro em safe_move_folder: {e}")
        return 0

def monta_caminho_contabil(customer_code, mes_ano_tuple):
    try:
        base = r"R:\Acesso Digital"
        empresa = next((p for p in os.listdir(base) if p.startswith(str(customer_code))), None)
        if not empresa:
            raise FileNotFoundError(f"Pasta com código {customer_code} não encontrada em {base}.")
        mes, ano = mes_ano_tuple
        destino = os.path.join(
            base, empresa, "02 - Contábil", ano,
            "01 - Fechamento Contábil", mes, "01 - Documentos do cliente"
        )
        return destino
    except Exception as e:
        logger.error(f"Erro em monta_caminho_contabil: {e}")
        return None

def monta_caminho_fiscal(customer_code, mes_ano_tuple):
    try:
        base = r"R:\Acesso Digital"
        empresa = next((p for p in os.listdir(base) if p.startswith(str(customer_code))), None)
        if not empresa:
            raise FileNotFoundError(f"Pasta com código {customer_code} não encontrada em {base}.")
        mes, ano = mes_ano_tuple
        destino = os.path.join(
            base, empresa, "01 - Fiscal", ano,
            "90 - Triagem de Documentos Mensal", mes, "10 - Backup (Winrar)"
        )
        return destino
    except Exception as e:
        logger.error(f"Erro em monta_caminho_fiscal: {e}")
        return None
