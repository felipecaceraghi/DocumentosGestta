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
    """Executa o processamento com a data atual"""
    try:
        logger.info("🤖 Iniciando processamento automático às 8:30...")
        
        # Obter data atual no formato YYYY-MM-DD
        current_date = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"📅 Processando tarefas para a data: {current_date}")
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(script_dir, 'main.py')
        
        # Executa o processo do main.py com a data atual
        result = subprocess.run([
            sys.executable, main_path, 
            '--start-date', current_date,
            '--end-date', current_date
        ], 
        capture_output=True, 
        text=True)
        
        if result.returncode == 0:
            logger.info("✅ Processamento automático concluído com sucesso")
            if result.stdout:
                logger.debug(f"Saída: {result.stdout}")
        else:
            logger.error(f"❌ Erro no processamento automático: código {result.returncode}")
            if result.stderr:
                logger.error(f"Erro: {result.stderr}")
    
    except Exception as e:
        logger.exception(f"💥 Erro durante o processamento automático: {str(e)}")

def calculate_next_run():
    """Calcula o próximo horário de execução (8:30 todos os dias)"""
    now = datetime.now()
    
    # Se ainda não passou das 8:30 hoje, próxima execução é hoje
    if now.hour < 8 or (now.hour == 8 and now.minute < 30):
        next_run_date = now.date()
    else:
        # Senão, próxima execução é amanhã
        next_run_date = (now + timedelta(days=1)).date()
    
    # Definir hora para 8:30
    next_run = datetime.combine(next_run_date, datetime.min.time().replace(hour=8, minute=30))
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
            sys.stdout.write(f"\r⏰ Próxima execução em: {days} dias, {hours:02d}:{minutes:02d}:{seconds:02d} (às 08:30 de {next_run.strftime('%d/%m/%Y')})")
            sys.stdout.flush()
            
            # Atualizar a cada segundo
            time.sleep(1)
    except Exception as e:
        logger.exception(f"Erro no cronômetro: {str(e)}")

def main():
    """Configura o scheduler para executar processamento todos os dias às 8:30"""
    try:
        logger.info("🚀 Iniciando o scheduler de processamento automático...")
        scheduler = BackgroundScheduler()
        job_id = 'execute_main_job'
        
        # Configurar para executar às 8:30 da manhã TODOS OS DIAS
        scheduler.add_job(
            execute_main,
            CronTrigger(
                hour=8, 
                minute=30
            ),
            id=job_id,
            name='Processamento automático de documentos Gestta às 8:30',
            replace_existing=True
        )
        
        # Iniciar o scheduler
        scheduler.start()
        logger.info("📅 Scheduler configurado: Execução DIÁRIA às 08:30 com data atual")
        
        # Mostrar o dia da semana atual para referência
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        dia_atual = dias[datetime.now().weekday()]
        logger.info(f"📆 Hoje é {dia_atual}")
        
        # Mostrar próxima execução
        next_run = calculate_next_run()
        logger.info(f"🎯 Próxima execução: {next_run.strftime('%d/%m/%Y às %H:%M')}")
        
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
            print("\n⏹️  Scheduler interrompido pelo usuário.")
        
    except Exception as e:
        logger.exception(f"Erro no scheduler: {str(e)}")

if __name__ == "__main__":
    main()