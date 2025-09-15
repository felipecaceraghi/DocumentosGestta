import os
import sys
import logging
import time
from datetime import datetime, timedelta
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess

# Configurar logging (usando seu sistema existente)
try:
    from logging_config import configure_logging
    configure_logging()
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('scheduler_logs.log')
        ]
    )

logger = logging.getLogger('scheduler')

def execute_main():
    """Executa o script main.py e registra o resultado"""
    try:
        logger.info("Iniciando execução do main.py...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(script_dir, 'main.py')
        
        # Executa o processo do main.py
        result = subprocess.run([sys.executable, main_path], 
                               capture_output=True, 
                               text=True)
        
        if result.returncode == 0:
            logger.info("Execução do main.py concluída com sucesso")
            if result.stdout:
                logger.debug(f"Saída: {result.stdout}")
        else:
            logger.error(f"Erro ao executar main.py: código {result.returncode}")
            if result.stderr:
                logger.error(f"Erro: {result.stderr}")
    
    except Exception as e:
        logger.exception(f"Erro durante a execução do main.py: {str(e)}")

def calculate_next_run():
    """Calcula o próximo horário de execução (5:00 no próximo dia útil)"""
    now = datetime.now()
    # Determinar o próximo dia útil
    if now.hour < 5 and now.weekday() < 5:  # Antes das 5:00 e dia útil (0-4 = seg-sex)
        next_run_date = now.date()
    elif now.weekday() < 4:  # Segunda a quinta, próximo dia é útil
        next_run_date = (now + timedelta(days=1)).date()
    elif now.weekday() == 4:  # Sexta, próximo dia útil é segunda
        next_run_date = (now + timedelta(days=3)).date()
    else:  # Final de semana
        days_until_monday = 7 - now.weekday()
        next_run_date = (now + timedelta(days=days_until_monday)).date()
    
    # Definir hora para 5:00
    next_run = datetime.combine(next_run_date, datetime.min.time().replace(hour=5))
    return next_run

def display_countdown(stop_event):
    """Exibe um cronômetro em tempo real até a próxima execução"""
    try:
        next_run = calculate_next_run()
        
        while not stop_event.is_set():
            now = datetime.now()
            time_diff = next_run - now
            
            # Verificar se já passou o horário previsto
            if time_diff.total_seconds() <= 0:
                next_run = calculate_next_run()  # Recalcular próxima execução
                continue
                
            days = time_diff.days
            seconds = time_diff.seconds
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            # Limpa a linha anterior e imprime o contador
            sys.stdout.write(f"\rPróxima execução em: {days} dias, {hours:02d}:{minutes:02d}:{seconds:02d} (às 05:00 de {next_run.strftime('%d/%m/%Y')})")
            sys.stdout.flush()
            
            # Atualizar a cada segundo
            time.sleep(1)
    except Exception as e:
        logger.exception(f"Erro no cronômetro: {str(e)}")

def main():
    """Configura o scheduler para executar main.py nos dias e horários especificados"""
    try:
        logger.info("Iniciando o scheduler...")
        scheduler = BackgroundScheduler()
        job_id = 'execute_main_job'
        
        # Configurar para executar às 5:00 da manhã de segunda a sexta
        scheduler.add_job(
            execute_main,
            CronTrigger(
                day_of_week='mon-fri',  # De segunda a sexta
                hour=5, 
                minute=0
            ),
            id=job_id,
            name='Execução do script main.py às 5:00',
            replace_existing=True
        )
        
        # Iniciar o scheduler
        scheduler.start()
        logger.info("Scheduler iniciado. Próxima execução será às 05:00 no próximo dia útil.")
        
        # Mostrar o dia da semana atual para referência
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        dia_atual = dias[datetime.now().weekday()]
        logger.info(f"Hoje é {dia_atual}")
        
        # Iniciar o cronômetro em uma thread separada
        stop_event = threading.Event()
        countdown_thread = threading.Thread(
            target=display_countdown, 
            args=(stop_event,)
        )
        countdown_thread.daemon = True
        countdown_thread.start()
        
        # Manter o programa rodando até que seja interrompido
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            stop_event.set()  # Sinaliza para o cronômetro parar
            scheduler.shutdown()
            print("\nScheduler interrompido pelo usuário.")
        
    except Exception as e:
        logger.exception(f"Erro no scheduler: {str(e)}")

if __name__ == "__main__":
    main()  