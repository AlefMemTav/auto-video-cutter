import os
import logging
import ffmpeg
from app.config.settings import settings

logger = logging.getLogger(__name__)

def extract_audio(job_id: str):
    """
    Extrai o áudio do vídeo input.mp4 e converte para WAV 16kHz Mono.
    Isso otimiza absurdamente a velocidade do Whisper.
    """
    job_folder = settings.get_job_path(job_id)
    
    # Path objects permitem usar o operador / para juntar caminhos
    input_video = job_folder / "input.mp4"
    output_audio = job_folder / "audio.wav"
    
    # Converter para string para o ffmpeg
    input_str = str(input_video)
    output_str = str(output_audio)

    logger.info(f"[{job_id}] Extraindo áudio de: {input_str}")

    if not input_video.exists():
        raise FileNotFoundError(f"Vídeo não encontrado: {input_str}")

    logger.info(f"[{job_id}] Extraindo áudio para: {output_str}")

    try:
        # Monta o comando FFmpeg:
        # -i input.mp4      (Input)
        # -vn               (No Video - descarta a imagem)
        # -ac 1             (Audio Channels 1 - Mono)
        # -ar 16000         (Audio Rate 16kHz - Padrão Whisper)
        # -y                (Overwrite - sobrescreve se existir)
        (
            ffmpeg
            .input(input_str)
            .output(output_str, acodec='pcm_s16le', ac=1, ar='16000')
            .overwrite_output()
            .run(quiet=True)
        )
        if not output_audio.exists():
            raise FileNotFoundError("O FFmpeg rodou mas não gerou o arquivo de áudio.")

        logger.info(f"✅ [{job_id}] Áudio extraído.")
        return output_str

    except ffmpeg.Error as e:
        logger.error(f"Erro FFmpeg: {e.stderr.decode('utf8') if e.stderr else str(e)}")
        raise e
    except Exception as e:
        logger.error(f"[{job_id}] Erro genérico na extração: {e}")
        raise e