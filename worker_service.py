import logging
from redis import Redis
from rq import Worker, Queue
from app.config.settings import settings

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_worker():
    redis_host = settings.REDIS_HOST
    redis_port = settings.REDIS_PORT
    queue_name = 'video_jobs'

    logger.info(f"🔌 Conectando ao Redis em {redis_host}:{redis_port}...")

    try:
        redis_conn = Redis(host=redis_host, port=redis_port)
        
        queue = Queue(queue_name, connection=redis_conn)
        
        worker = Worker([queue], connection=redis_conn)
        
        logger.info(f"👷 Worker iniciado! Escutando a fila: '{queue_name}'")
        
        worker.work()
        
    except Exception as e:
        logger.error(f"❌ Erro fatal no Worker: {e}")
        raise e

if __name__ == '__main__':
    start_worker()