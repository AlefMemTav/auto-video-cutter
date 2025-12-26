import ffmpeg
import logging
from pathlib import Path
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_audio(job_id: str) -> Path:
    """
    Extrai o áudio do vídeo input.mp4 e converte para WAV 16kHz Mono.
    Isso otimiza absurdamente a velocidade do Whisper.
    """
    job_folder = settings.get_job_path(job_id)
    input_video = job_folder / "input.mp4"
    output_audio = job_folder / "audio.wav"

    if not input_video.exists():
        raise FileNotFoundError(f"Vídeo não encontrado para extração: {input_video}")

    logger.info(f"[{job_id}] Extraindo áudio para: {output_audio}")

    try:
        # Monta o comando FFmpeg:
        # -i input.mp4      (Input)
        # -vn               (No Video - descarta a imagem)
        # -ac 1             (Audio Channels 1 - Mono)
        # -ar 16000         (Audio Rate 16kHz - Padrão Whisper)
        # -y                (Overwrite - sobrescreve se existir)
        (
            ffmpeg
            .input(str(input_video))
            .output(str(output_audio), ac=1, ar=16000)
            .overwrite_output()
            .run(quiet=True) # quiet=True esconde o log gigante do ffmpeg no terminal
        )
        
        if not output_audio.exists():
            raise FileNotFoundError("O FFmpeg rodou mas não gerou o arquivo de áudio.")

        logger.info(f"[{job_id}] Áudio extraído com sucesso.")
        return output_audio

    except ffmpeg.Error as e:
        logger.error(f"[{job_id}] Erro no FFmpeg: {e.stderr.decode('utf8') if e.stderr else str(e)}")
        raise e
    except Exception as e:
        logger.error(f"[{job_id}] Erro genérico na extração: {e}")
        raise e