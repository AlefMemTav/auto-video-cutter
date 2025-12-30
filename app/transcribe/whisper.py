import json
import logging
import os
import torch
from faster_whisper import WhisperModel
from app.config.settings import settings

logger = logging.getLogger(__name__)

def get_device_config():
    """
    Decide inteligentemente qual hardware usar.
    Retorna (device, compute_type)
    """
    env_device = os.getenv("WHISPER_DEVICE", "auto").lower()

    # 1. Se o usuário forçou CPU via variável de ambiente
    if env_device == "cpu":
        return "cpu", "int8"

    # 2. Se detectar CUDA disponível (NVIDIA)
    if torch.cuda.is_available():
        try:
            # Tenta pegar info da placa para saber se é robusta (ex: Tesla/RTX) ou Entrada (MX)
            props = torch.cuda.get_device_properties(0)
            logger.info(f"🖥️  GPU Detectada: {props.name} (VRAM: {props.total_memory / 1024**3:.1f} GB)")
            
            # Placas MX ou antigas geralmente travam com float16. 
            # Vamos forçar float32 ou int8 para segurança máxima.
            return "cuda", "float32" # float32 é o "Doador Universal", funciona sempre.
            
        except Exception:
            # Se não conseguir ler a placa, vai no seguro
            return "cuda", "float32"

    # 3. Fallback para CPU
    logger.warning("⚠️ Nenhuma GPU NVIDIA detectada ou configurada. Usando CPU (será mais lento).")
    return "cpu", "int8"

def transcribe_audio(job_id: str):
    logger.info(f"[{job_id}] Iniciando transcrição com Faster-Whisper...")
    
    job_dir = settings.get_job_path(job_id)
    audio_path = job_dir / "audio.wav"
    output_path = job_dir / "transcript.json"

    device, compute_type = get_device_config()
    
    compute_type = "float32" 

    logger.info(f"[{job_id}] Iniciando Whisper | Device: {device} | Type: {compute_type}")
    
    try:
        # Carrega o modelo Faster-Whisper
        model = WhisperModel("small", device=device, compute_type=compute_type)

        segments, info = model.transcribe(
            str(audio_path), 
            beam_size=5, 
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            language="pt"
        )

        formatted_result = {"segments": []}
        
        # Iteração com logs detalhados
        for i, segment in enumerate(segments):
            # Log para provar que está funcionando
            if i % 10 == 0:
                logger.info(f"🗣️  Segmento {i}: {segment.text[:40]}...")

            segment_dict = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": []
            }
            
            if segment.words:
                for word in segment.words:
                    segment_dict["words"].append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "score": word.probability
                    })
            
            formatted_result["segments"].append(segment_dict)

        # Salva o JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(formatted_result, f, indent=2, ensure_ascii=False)

        total_words = sum(len(s['words']) for s in formatted_result['segments'])
        logger.info(f"[{job_id}] Transcrição salva! Total de palavras processadas: {total_words}")

        if total_words == 0:
            logger.warning(f"⚠️ AVISO CRÍTICO: 0 palavras. Se isso persistir com float32, o áudio.wav pode estar mudo.")

    except Exception as e:
        logger.error(f"Erro fatal na transcrição: {e}")
        raise e