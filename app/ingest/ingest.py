import yt_dlp
import logging
from pathlib import Path
from app.settings import settings

# Configuração básica de log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_video(url: str, job_id: str) -> Path:
    """
    Baixa o vídeo do YouTube na melhor qualidade compatível (MP4).
    Retorna o caminho do arquivo de vídeo baixado.
    """
    job_folder = settings.get_job_path(job_id)
    output_template = str(job_folder / "input.%(ext)s")

    logger.info(f"[{job_id}] Iniciando download: {url}")

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        # Otimizações para não baixar thumbnails ou metadados inúteis
        'writethumbnail': False,
        'writeinfojson': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Encontrar o arquivo baixado (yt-dlp pode mudar a extensão ligeiramente)
        # Procuramos qualquer arquivo que comece com "input" na pasta
        video_path = next(job_folder.glob("input.*"), None)
        
        if not video_path:
            raise FileNotFoundError("O arquivo não foi encontrado após o download.")
            
        logger.info(f"[{job_id}] Download concluído: {video_path}")
        return video_path

    except Exception as e:
        logger.error(f"[{job_id}] Erro no download: {e}")
        raise e