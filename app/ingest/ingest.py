import os
import glob
import logging
import subprocess
import yt_dlp

# Configuração básica de log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def standardize_video(input_path: str, output_path: str):
    """
    Converte para MP4 H.264 / AAC.
    """
    logger.info(f"🔄 Padronizando vídeo para H.264...")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Arquivo de entrada não existe: {input_path}")

    # Detecta se é necessário redimensionar para economizar CPU
    # Se o vídeo for > 1080p, o ffmpeg vai gastar muito tempo a toa.
    # O filtro scale só aplica se for necessário, mas aqui vamos confiar no download.

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",  # Velocidade máxima
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        output_path,
    ]

    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        logger.info(f"✅ Vídeo padronizado: {output_path}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Erro na padronização: {e.stderr.decode()}")
        raise e


def ingest_video(source: str, job_folder: str) -> str:
    final_output_path = os.path.join(job_folder, "input.mp4")

    # Prefixo para busca
    temp_prefix = os.path.join(job_folder, "raw_temp")

    # --- CENÁRIO 1: DOWNLOAD YOUTUBE OTIMIZADO ---
    if source.startswith(("http://", "https://", "www.")):
        logger.info(f"🌐 Detectada URL. Baixando via yt-dlp: {source}")

        # OTIMIZAÇÃO DE FORMATO:
        # 1. bestvideo[height<=1080]: Não baixa 4K (enorme economia de tempo/CPU).
        # 2. [ext=mp4]: Tenta pegar nativamente em MP4 se existir.
        # 3. /best[ext=mp4]: Fallback para melhor mp4 único.
        ydl_opts = {
            "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": temp_prefix + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "writethumbnail": False,
            "writeinfojson": False,
        }

        try:
            # Baixa
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([source])

            # Localiza o arquivo baixado (mp4, mkv ou webm)
            found_files = glob.glob(temp_prefix + ".*")

            if not found_files:
                raise FileNotFoundError(
                    "Erro: yt-dlp finalizou mas nenhum arquivo foi encontrado."
                )

            downloaded_file = found_files[0]
            logger.info(f"📁 Download concluído: {downloaded_file}")

            # Converte/Padroniza
            standardize_video(downloaded_file, final_output_path)

            # Limpa o bruto
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)

            return final_output_path

        except Exception as e:
            logger.error(f"Erro no ingest (YouTube): {e}")
            raise e

    # --- CENÁRIO 2: ARQUIVO LOCAL ---
    else:
        source_path = os.path.join("/app/inputs", source)
        logger.info(f"📂 Arquivo local: {source_path}")

        if not os.path.exists(source_path):
            error_msg = f"Arquivo não encontrado: {source}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            standardize_video(source_path, final_output_path)
            return final_output_path

        except Exception as e:
            logger.error(f"Erro no ingest (Local): {e}")
            raise e
