import subprocess
import logging
from pathlib import Path
from app.config.settings import settings
from app.subtitles.ass_generator import create_ass_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def render_short(job_id: str, segment_index: int, segment_data: dict, options: dict = None) -> Path:
    if options is None:
        options = {}

    job_folder = settings.get_job_path(job_id)
    input_video = job_folder / "input.mp4"
    
    # Cria pastas
    subs_folder = job_folder / "subtitles"
    outputs_folder = job_folder / "outputs"
    subs_folder.mkdir(exist_ok=True)
    outputs_folder.mkdir(exist_ok=True)

    output_video = outputs_folder / f"short_{segment_index:03d}.mp4"
    ass_path = subs_folder / f"seg_{segment_index:03d}.ass"

    # Pega as opções
    video_format = options.get('format', 'vertical')
    use_subs = options.get('use_subs', True) # Padrão True se não vier nada

    logger.info(f"[{job_id}] Renderizando Short #{segment_index} (Subs: {use_subs})")

    # 1. Monta o filtro visual BASE (Corte e Proporção)
    if video_format == 'vertical':
        # Blur + Crop Vertical
        base_filter = (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg_blurred];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg_scaled];"
            "[bg_blurred][fg_scaled]overlay=(W-w)/2:(H-h)/2[base_out]"
        )
    else:
        # Horizontal (1920x1080)
        base_filter = (
            f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[base_out]"
        )

    # 2. Decide se aplica legenda ou não
    if use_subs:
        # Gera o arquivo .ass
        res_x = 1920 if video_format == 'horizontal' else 1080
        res_y = 1080 if video_format == 'horizontal' else 1920
        options['res_x'] = res_x
        options['res_y'] = res_y
        
        create_ass_file(segment_data, ass_path, options=options)
        
        # Concatena o filtro de legenda no vídeo base
        # Pega [base_out], aplica legenda e manda para [outv]
        final_filter = f"{base_filter};[base_out]ass='{ass_path}'[outv]"
    else:
        # Sem legenda: apenas passa o [base_out] direto para o [outv]
        # Usamos o filtro 'null' que não faz nada, só para manter a consistência do nome [outv]
        final_filter = f"{base_filter};[base_out]null[outv]"

    # 3. Comando
    cmd = [
        'ffmpeg', 
        '-y',
        '-ss', str(segment_data['start']),
        '-t', str(segment_data['duration']),
        '-i', str(input_video),
        '-filter_complex', final_filter,
        '-map', '[outv]',
        '-map', '0:a',
        '-c:v', 'libx264', 
        '-preset', 'ultrafast',
        '-c:a', 'aac', 
        '-b:a', '128k',
        str(output_video)
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return output_video
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro FFmpeg: {e.stderr.decode()}")
        raise e