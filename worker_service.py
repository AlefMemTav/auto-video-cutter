import sys
import logging
from redis import Redis
from rq import Worker, Queue, Connection
from app.config.queue import redis_conn

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_worker():
    """
    Inicia um Worker que fica escutando a fila 'video_jobs'.
    """
    queues = ['video_jobs']
    
    logger.info("=======================================")
    logger.info("👷 WORKER DOCKER INICIADO!")
    logger.info("🚀 Ambiente: CUDA")
    logger.info("📥 Aguardando jobs na fila 'video_jobs'...")
    logger.info("=======================================")
    
    # Estabelece conexão e inicia o trabalho
    with Connection(redis_conn):
        worker = Worker(queues)
        worker.work()

if __name__ == '__main__':
    try:
        start_worker()
    except KeyboardInterrupt:
        logger.info("\n🛑 Worker parando...")
        sys.exit()