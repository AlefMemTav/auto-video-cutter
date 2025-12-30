import subprocess
import logging
import statistics
import os
import cv2
import math

from pathlib import Path
from typing import Tuple, Optional

from app.config.settings import settings
from app.subtitles.ass_generator import create_ass_file
from app.video.smart_crop import get_smart_crop_coordinates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_video_dims(video_path: str) -> Tuple[Optional[int], Optional[int]]:
    """Retorna (width, height) do vídeo original."""
    try:
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return None, None

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()
        return w, h

    except Exception as e:
        logger.error(f"Erro ao ler dimensões: {e}")
        return None, None


def render_short(
    job_id: str, segment_index: int, segment_data: dict, options: dict = None
) -> Path:
    if options is None:
        options = {}

    job_folder = settings.get_job_path(job_id)
    input_video = job_folder / "input.mp4"

    subs_folder = job_folder / "subtitles"
    outputs_folder = job_folder / "outputs"

    subs_folder.mkdir(exist_ok=True)
    outputs_folder.mkdir(exist_ok=True)

    output_video = outputs_folder / f"short_{segment_index:03d}.mp4"
    ass_path = subs_folder / f"seg_{segment_index:03d}.ass"

    video_format = options.get("format", "vertical")
    use_subs = options.get("use_subs", True)
    use_blur = options.get("use_blur", False)

    logger.info(f"[{job_id}] Renderizando Short #{segment_index} (Subs: {use_subs})")

    base_filter = ""

    if video_format == "vertical":
        target_w = 1080
        target_h = 1920

        if use_blur:
            # Estratégia: Fundo desfocado com vídeo original centralizado
            base_filter = (
                "[0:v]split=2[bg][fg];"
                f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},boxblur=20:10[bg_blurred];"
                f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg_scaled];"
                "[bg_blurred][fg_scaled]overlay=(W-w)/2:(H-h)/2[base_out]"
            )
        else:
            # --- SMART CROP OTIMIZADO ---
            orig_w, orig_h = get_video_dims(str(input_video))

            # 1. Calcular o fator de escala correto para PREENCHER a tela
            # Usamos max() para garantir que NENHUM lado fique menor que o alvo
            scale_w = target_w / orig_w
            scale_h = target_h / orig_h
            scale_factor = max(scale_w, scale_h)

            # Novas dimensões após o redimensionamento
            new_w = math.ceil(orig_w * scale_factor)
            new_h = math.ceil(orig_h * scale_factor)

            # Garantir que sejam pares (FFmpeg gosta de pares)
            if new_w % 2 != 0:
                new_w += 1
            if new_h % 2 != 0:
                new_h += 1

            logger.info(
                f"📐 Dimensões: Orig={orig_w}x{orig_h} -> New={new_w}x{new_h} (Alvo 1080x1920)"
            )

            final_crop_x = 0

            # Só roda detecção inteligente se tivermos largura sobrando para "panear"
            # Se new_w for muito próximo de 1080, apenas centralizamos.
            if new_w > target_w + 10:
                crop_centers_list = get_smart_crop_coordinates(
                    str(input_video),
                    segment_data["duration"],
                    segment_data["start"],
                    segment_data["end"],
                )

                if crop_centers_list:
                    try:
                        avg_center_original = statistics.median(crop_centers_list)

                        # Converte o centro original para a nova escala
                        scaled_center_x = avg_center_original * scale_factor

                        # Calcula o canto esquerdo (Top-Left X)
                        calculated_x = int(scaled_center_x - (target_w / 2))

                        # Limita para não sair da borda (Clamp)
                        max_x = new_w - target_w
                        final_crop_x = max(0, min(calculated_x, max_x))

                        logger.info(
                            f"🎯 Smart Crop: X calculado={final_crop_x} (Max possível={max_x})"
                        )
                    except Exception as e:
                        logger.error(f"Erro matemática Smart Crop: {e}")
                        final_crop_x = (new_w - target_w) // 2  # Centraliza fallback
                else:
                    final_crop_x = (new_w - target_w) // 2  # Centraliza fallback
            else:
                # Se o vídeo já é vertical "apertado", centraliza o excedente mínimo
                final_crop_x = (new_w - target_w) // 2
                logger.info(
                    f"⚠️ Vídeo estreito, forçando centralização. Crop X={final_crop_x}"
                )

            # Filtro com dimensões calculadas explicitamente
            base_filter = f"[0:v]scale={new_w}:{new_h},crop={target_w}:{target_h}:{final_crop_x}:0[base_out]"
    else:
        # Formato Horizontal (1920x1080) com padding se necessário
        base_filter = f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[base_out]"

    # --- Lógica de Legendas ---
    if use_subs:
        # Define resolução de referência para o gerador de legendas
        options["res_x"] = 1920 if video_format == "horizontal" else 1080
        options["res_y"] = 1080 if video_format == "horizontal" else 1920

        create_ass_file(segment_data, ass_path, options=options)

        # Adiciona o filtro de legendas na pipeline
        # [base_out] -> Legendas -> [outv]
        final_filter = f"{base_filter};[base_out]ass='{ass_path}':fontsdir='/app/assets/fonts'[outv]"
    else:
        # Apenas passa o stream adiante (usando null filter para manter consistência de nomes)
        final_filter = f"{base_filter};[base_out]null[outv]"

    # --- Montagem do Comando FFmpeg ---
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(segment_data["start"]),
        "-t",
        str(segment_data["duration"]),
        "-i",
        str(input_video),
        "-filter_complex",
        final_filter,
        "-map",
        "[outv]",  # Mapeia o vídeo processado
        "-map",
        "0:a",  # Mapeia o áudio original
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_video),
    ]

    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        return output_video
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro FFmpeg: {e.stderr.decode()}")
        raise e
