import logging
import uuid
import json
from app.ingest.ingest import download_video
from app.audio.extract_audio import extract_audio
from app.transcribe.whisper import transcribe_audio
from app.segment.segmenter import segment_transcript
from app.render.renderer import render_short

# Configuração de Log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_video_pipeline(url: str, job_id: str = None):
    """
    Executa o pipeline completo de transformação de vídeo.
    Versão compatível com segmentador funcional.
    """
    if not job_id:
        job_id = str(uuid.uuid4())
    
    logger.info(f"🚀 [JOB {job_id}] Iniciando pipeline para: {url}")

    try:
        # 1. Ingestão (Download)
        logger.info(f"--- ETAPA 1: DOWNLOAD ---")
        download_video(url, job_id)

        # 2. Extração de Áudio
        logger.info(f"--- ETAPA 2: EXTRAÇÃO DE ÁUDIO ---")
        extract_audio(job_id)

        # 3. Transcrição (Whisper)
        logger.info(f"--- ETAPA 3: TRANSCRIÇÃO (ISSO PODE DEMORAR) ---")
        transcribe_audio(job_id)

        # 4. Segmentação (Heurística)
        logger.info(f"--- ETAPA 4: SEGMENTAÇÃO ---")
        
        # Chama a função que já cria o segments.json e retorna o caminho dele
        segments_path = segment_transcript(job_id)
        
        # Agora carregamos esse arquivo JSON para poder ler os cortes
        with open(segments_path, 'r', encoding='utf-8') as f:
            segments = json.load(f)
        
        total_cuts = len(segments)
        logger.info(f"✂️  Encontrados {total_cuts} cortes potenciais.")

        # 5. Renderização (Loop)
        logger.info(f"--- ETAPA 5: RENDERIZAÇÃO ---")
        
        # Limite de segurança para testes (renderiza só os 3 primeiros)
        # Mude para "limit = total_cuts" quando quiser processar tudo
        limit = 3 
        
        for i, segment in enumerate(segments[:limit]):
            idx = i + 1
            logger.info(f"🎥 Renderizando Short {idx}/{limit} (Total: {total_cuts})...")
            
            # Como o segmenter já salva em JSON (dict), podemos passar direto
            render_short(job_id, idx, segment)

        logger.info(f"✅ [JOB {job_id}] Pipeline finalizado com sucesso!")
        return job_id

    except Exception as e:
        logger.error(f"❌ [JOB {job_id}] Falha crítica: {e}", exc_info=True)
        raise e