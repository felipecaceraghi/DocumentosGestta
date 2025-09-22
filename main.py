# main.py
import os
import sys
import argparse
from logger_config import logger
from processing import programar_verificacoes, realizar_processamento
from PyQt5.QtWidgets import QApplication
from gui import GesttaConfigurador, set_app_style
from logging_config import configure_logging
from config import DEBUG_MODE

def parse_args():
    parser = argparse.ArgumentParser(description='Sistema de processamento de documentos Gestta')
    parser.add_argument('--config', action='store_true', help='Executar configurador')
    parser.add_argument('--start-date', help='Data inicial para busca (formato: YYYY-MM-DD)')
    parser.add_argument('--end-date', help='Data final para busca (formato: YYYY-MM-DD)')
    return parser.parse_args()

def main():
    # Configure logging with Unicode support
    logger = configure_logging()
    logger.info("Iniciando aplicação de processamento de documentos Gestta")
    
    args = parse_args()
    
    if args.config:
        app = QApplication(sys.argv)
        set_app_style(app)
        window = GesttaConfigurador()
        window.show()
        sys.exit(app.exec_())
    else:
        try:
            logger.info("Iniciando sistema de cobrança de documentos Gestta...")
            logger.info("Para configurar o sistema, execute com a opção --config")
            if not os.path.exists("gestta_config.json"):
                logger.error("Arquivo de configuração 'gestta_config.json' não encontrado.")
                logger.error("Por favor, execute 'python main.py --config' primeiro.")
                sys.exit(1)
            
            if args.start_date or args.end_date:
                logger.info(f"Executando com datas personalizadas:")
                logger.info(f"Data inicial: {args.start_date or 'hoje'}")
                logger.info(f"Data final: {args.end_date or args.start_date or 'hoje'}")
                realizar_processamento(args.start_date, args.end_date)
            else:
                programar_verificacoes()
        except KeyboardInterrupt:
            logger.info("Sistema encerrado pelo usuário.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Erro fatal ao iniciar o sistema: {str(e)}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()
