import os
from redis import Redis
from rq import Queue

# Pega o host da variável de ambiente ou usa localhost (fallback)
redis_host = os.getenv('REDIS_HOST', 'localhost')

# Conecta no Redis
redis_conn = Redis(host=redis_host, port=6379)

# Cria a fila
video_queue = Queue('video_jobs', connection=redis_conn)