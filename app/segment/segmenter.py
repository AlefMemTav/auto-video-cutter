import json
import logging
from pathlib import Path
from app.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações de tempo para Shorts (em segundos)
MIN_DURATION = 30.0
MAX_DURATION = 60.0

def load_transcript(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_segments(segments, job_id: str):
    job_folder = settings.get_job_path(job_id)
    output_path = job_folder / "segments.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    return output_path

def segment_transcript(job_id: str) -> Path:
    """
    Lê o transcript.json e agrupa frases baseadas em tempo e pontuação.
    Gera o segments.json.
    """
    job_folder = settings.get_job_path(job_id)
    transcript_path = job_folder / "transcript.json"
    
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript não encontrado: {transcript_path}")

    logger.info(f"[{job_id}] Iniciando segmentação heurística...")
    transcript = load_transcript(transcript_path)

    final_segments = []
    
    # Variáveis temporárias para construir o bloco atual
    current_block = []
    current_start = 0.0
    
    for i, phrase in enumerate(transcript):
        # Se for o início de um bloco novo
        if not current_block:
            current_start = phrase['start']
        
        current_block.append(phrase)
        
        current_end = phrase['end']
        current_duration = current_end - current_start
        text = phrase['text'].strip()

        # Verifica se é hora de fechar o bloco
        is_valid_duration = MIN_DURATION <= current_duration <= MAX_DURATION
        is_max_limit = current_duration > MAX_DURATION
        has_strong_punctuation = text.endswith('.') or text.endswith('?') or text.endswith('!')
        
        # LOGICA DE CORTE:
        # 1. Se estiver no tempo ideal E tiver pontuação final -> CORTA (Melhor cenário)
        # 2. Se estourou o tempo máximo -> CORTA (Cenário forçado)
        
        should_cut = (is_valid_duration and has_strong_punctuation) or is_max_limit

        if should_cut:
            # Salva o segmento
            segment_text = " ".join([p['text'].strip() for p in current_block])
            
            final_segments.append({
                "start": current_start,
                "end": current_end,
                "duration": current_duration,
                "text": segment_text,
                # Salvamos as palavras originais para poder legendar com precisão depois
                "words": [w for p in current_block for w in p.get('words', [])]
            })
            
            # Reseta para o próximo bloco
            current_block = []
            # Log para debug visual
            # logger.info(f"Corte encontrado: {current_duration:.1f}s -> {segment_text[:50]}...")

    # Salva o resultado
    output_path = save_segments(final_segments, job_id)
    logger.info(f"[{job_id}] Segmentação concluída. {len(final_segments)} cortes gerados.")
    return output_path