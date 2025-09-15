import json
import os
from logger_config import logger

def load_config():
    """Carrega as configurações do sistema do arquivo gestta_config.json"""
    try:
        if os.path.exists('gestta_config.json'):
            with open('gestta_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        else:
            logger.error("Arquivo de configuração 'gestta_config.json' não encontrado")
            return {}
    except Exception as e:
        logger.error(f"Erro ao carregar configuração: {str(e)}")
        return {}

def get_debug_mode():
    """Verifica se o modo debug está ativado nas configurações"""
    config = load_config()
    return config.get('debug_mode', False)

def save_config(config):
    """Salva as configurações no arquivo gestta_config.json"""
    try:
        with open('gestta_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar configuração: {str(e)}")
        return False
