import logging
from pathlib import Path
from faster_whisper import WhisperModel
from app.config.settings import settings
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def transcribe_audio(job_id: str) -> Path:
    """
    Transcreve o áudio usando faster-whisper.
    Retorna o caminho do arquivo JSON com os segmentos.
    """
    job_folder = settings.get_job_path(job_id)
    audio_path = job_folder / "audio.wav"
    output_json = job_folder / "transcript.json"

    if not audio_path.exists():
        raise FileNotFoundError(f"Áudio não encontrado: {audio_path}")

    logger.info(f"[{job_id}] Carregando modelo Whisper ({settings.WHISPER_MODEL}) na {settings.WHISPER_DEVICE}...")
    
    # Carrega o modelo (na primeira vez vai baixar, demora um pouco)
    model = WhisperModel(
        settings.WHISPER_MODEL, 
        device=settings.WHISPER_DEVICE, 
        compute_type="int8" # Use 'int8' para CPU ou 'float16' para GPU
    )

    logger.info(f"[{job_id}] Iniciando transcrição...")
    
    # Executa a transcrição
    # word_timestamps=True é fundamental para cortes precisos
    segments, info = model.transcribe(str(audio_path), word_timestamps=True, language="pt")

    # Formata a saída para uma lista simples de dicionários
    transcript_data = []
    
    # O 'segments' é um gerador, a transcrição acontece enquanto iteramos aqui:
    for segment in segments:
        seg_data = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "words": [
                {"start": w.start, "end": w.end, "word": w.word.strip()} 
                for w in segment.words
            ]
        }
        transcript_data.append(seg_data)
        # Log de progresso simples (opcional)
        # print(f"{segment.start:.2f}s: {segment.text}")

    # Salva em JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    logger.info(f"[{job_id}] Transcrição salva em: {output_json}")
    return output_json