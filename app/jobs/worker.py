import logging
import uuid
import os
from redis import Redis
from app.config.settings import settings
from app.ingest.ingest import ingest_video
from app.audio.extract_audio import extract_audio
from app.transcribe.whisper import transcribe_audio
from app.segment.segmenter import Segmenter, load_phrases, save_segments
from app.render.renderer import render_short

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Removemos a conexão global 'r_status' aqui para evitar desconexão no fork

def update_progress(job_id, progress, status_text):
    """Salva o progresso no Redis de forma segura"""
    try:
        # Conecta a cada chamada para garantir thread-safety
        r = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        
        r.hset(f"job_status:{job_id}", mapping={
            "progress": progress,
            "status": status_text
        })
        r.expire(f"job_status:{job_id}", 3600)
    except Exception as e:
        logger.error(f"Erro ao atualizar Redis: {e}")

def process_video_pipeline(video_source: str, job_id: str = None, options: dict = None):
    if not job_id:
        job_id = str(uuid.uuid4())
    if options is None:
        options = {}

    min_dur = options.get('min_duration', 30.0)
    max_dur = options.get('max_duration', 60.0)

    # Usamos o settings para pegar o caminho absoluto correto (/app/storage/jobs/ID)
    # O método get_job_path já cria a pasta automaticamente (mkdir)
    job_folder_path = settings.get_job_path(job_id)
    
    # Convertemos para string para passar para as funções que esperam texto
    job_folder = str(job_folder_path)
    
    logger.info(f"🚀 [JOB {job_id}] Iniciando pipeline...")
    logger.info(f"📂 Pasta do Job: {job_folder}")

    try:
        # 1. Ingestão
        logger.info(f"--- ETAPA 1: INGESTÃO ---")
        update_progress(job_id, 10, "Recebendo vídeo...")
        ingest_video(video_source, job_folder)

        # 2. Audio
        logger.info(f"--- ETAPA 2: EXTRAÇÃO DE ÁUDIO ---")
        update_progress(job_id, 30, "Extraindo áudio...")
        extract_audio(job_id)

        # 3. Transcrição
        logger.info(f"--- ETAPA 3: TRANSCRIÇÃO ---")
        update_progress(job_id, 50, "Transcrevendo com Whisper (Isso pode demorar)...")
        transcribe_audio(job_id)

        # 4. Segmentação
        logger.info(f"--- ETAPA 4: SEGMENTAÇÃO ---")
        update_progress(job_id, 70, "Analisando cortes...")
        # Carrega frases do JSON
        phrases = load_phrases(job_id)
        
        # Instancia o segmentador e processa
        segmenter = Segmenter(min_duration=min_dur, max_duration=max_dur)
        segments_objects = segmenter.segment(phrases)
        # Salva o resultado
        save_segments(segments_objects, job_id)
        
        total_cuts = len(segments_objects)
        logger.info(f"✂️  Encontrados {total_cuts} cortes.")

        if total_cuts == 0:
            logger.warning("⚠️ Nenhum corte encontrado!")
            return job_id

        # 5. Renderização
        logger.info(f"--- ETAPA 5: RENDERIZAÇÃO ---")
        limit = total_cuts
        
        for i, seg in enumerate(segments_objects[:limit]):
            idx = i + 1
            logger.info(f"🎥 Renderizando Short {idx}/{limit}...")
            
            current_pct = 70 + int((i / total_cuts) * 25)
            update_progress(job_id, current_pct, f"Renderizando Clip {i+1}/{total_cuts}...")
           
            # Converte objeto Segment para dict para o renderizador 
            seg_dict = {
                "start": seg.start,
                "end": seg.end,
                "duration": seg.duration,
                "text": seg.text,
                "words": seg.words
            }
            render_short(job_id, idx, seg_dict, options=options)
        
        update_progress(job_id, 100, "Finalizado!")
        logger.info(f"✅ [JOB {job_id}] Pipeline finalizado com sucesso!")
        return job_id

    except Exception as e:
        logger.error(f"❌ [JOB {job_id}] Falha crítica: {e}", exc_info=True)
        raise e