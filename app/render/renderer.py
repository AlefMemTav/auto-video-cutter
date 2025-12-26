import subprocess
import logging
from pathlib import Path
from app.config.settings import settings
from app.subtitles.ass_generator import create_ass_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def render_short(job_id: str, segment_index: int, segment_data: dict) -> Path:
    """
    Renderiza um único short a partir dos dados do segmento.
    """
    job_folder = settings.get_job_path(job_id)
    input_video = job_folder / "input.mp4"
    
    # Cria pastas de saída se não existirem
    subs_folder = job_folder / "subtitles"
    outputs_folder = job_folder / "outputs"
    subs_folder.mkdir(exist_ok=True)
    outputs_folder.mkdir(exist_ok=True)

    # Nomes dos arquivos
    ass_path = subs_folder / f"seg_{segment_index:03d}.ass"
    output_video = outputs_folder / f"short_{segment_index:03d}.mp4"

    # 1. Gerar a legenda para este segmento
    create_ass_file(segment_data, ass_path)

    logger.info(f"[{job_id}] Renderizando Short #{segment_index}...")

    # Tempos de corte
    start = segment_data['start']
    duration = segment_data['duration']

    # --- COMANDO FFMPEG ---
    # Explicação:
    # -ss / -t: Corta o vídeo original RAPIDO (antes de decodificar)
    # [0:v]split: Duplica o vídeo
    # [bg]: Escala para preencher 1080x1920 e aplica Blur
    # [fg]: Escala para largura 1080 (proporcional)
    # overlay: Cola o [fg] no centro do [bg]
    # ass: Aplica a legenda POR CIMA de tudo
    
    filter_complex = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg_blurred];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg_scaled];"
        "[bg_blurred][fg_scaled]overlay=(W-w)/2:(H-h)/2[composed];"
        f"[composed]ass='{ass_path}'[outv]"
    )

    cmd = [
        'ffmpeg',
        '-y',               # Sobrescrever
        '-ss', str(start),  # Início do corte
        '-t', str(duration),# Duração
        '-i', str(input_video),
        '-filter_complex', filter_complex,
        '-map', '[outv]',   # Mapeia o vídeo processado
        '-map', '0:a',      # Mapeia o áudio original
        '-c:v', 'libx264',
        '-preset', 'ultrafast', # Use 'medium' para produção final (mais lento, melhor qualidade)
        '-c:a', 'aac',
        '-b:a', '128k',
        str(output_video)
    ]

    try:
        # Executa e esconde o log do ffmpeg, mostra apenas erros
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logger.info(f"[{job_id}] Short salvo em: {output_video}")
        return output_video
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro FFmpeg: {e.stderr.decode()}")
        raise e