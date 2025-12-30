import cv2
import mediapipe as mp
import numpy as np
import logging

logger = logging.getLogger(__name__)

def get_smart_crop_coordinates(video_path, duration, segment_start, segment_end):
    """
    Analisa o vídeo e retorna uma lista de coordenadas X (centro) para cada frame.
    Se o MediaPipe falhar, retorna o centro estático (Fallback).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Erro ao abrir vídeo para Smart Crop.")
        return None

    # Propriedades do vídeo
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Define o alvo (9:16)
    target_aspect = 9 / 16
    target_width = int(height * target_aspect)
    
    # Centro padrão (para caso de falha)
    default_center_x = width // 2

    # Configuração do intervalo de análise (para não ler o vídeo todo à toa)
    start_frame = int(segment_start * fps)
    end_frame = int(segment_end * fps)
    total_frames_to_scan = end_frame - start_frame
    
    mp_face_detection = None
    face_detection = None
    
    try:
        mp_face_detection = mp.solutions.face_detection
        face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.6)
        logger.info("🤖 Smart Crop: MediaPipe iniciado com sucesso.")
    except Exception as e:
        logger.error(f"⚠️ Erro ao iniciar MediaPipe: {e}. Usando corte centralizado padrão.")
        # Se falhar aqui, retornamos None e o renderer deve lidar com isso, 
        # ou retornamos um valor fixo. Vamos retornar fixo para garantir.
        return [default_center_x] * total_frames_to_scan

    # Pula para o início do segmento
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    centers = []
    
    # Suavização (Exponencial)
    last_center_x = default_center_x
    smoothing_factor = 0.1  # Quanto menor, mais suave a câmera (menos tremida)

    frames_read = 0
    
    while cap.isOpened() and frames_read < total_frames_to_scan:
        success, image = cap.read()
        if not success:
            break

        frames_read += 1
        
        # Otimização: Analisar 1 a cada 2 ou 3 frames para ganhar velocidade
        # Mas para suavidade perfeita, analisamos todos ou interpolamos.
        # Vamos analisar todos por enquanto.

        current_center = last_center_x

        try:
            # Converte BGR para RGB
            image.flags.writeable = False
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = face_detection.process(image_rgb)
            
            if results.detections:
                # Pega o maior rosto (maior score)
                best_detection = max(results.detections, key=lambda d: d.score[0])
                
                # Bounding Box relativa (0.0 a 1.0)
                bboxC = best_detection.location_data.relative_bounding_box
                
                # Calcula o centro do rosto em pixels
                center_x_pixel = int((bboxC.xmin + bboxC.width / 2) * width)
                
                # Atualiza o alvo
                current_center = center_x_pixel
            
        except Exception:
            # Se der erro num frame específico, mantém o anterior
            pass
        
        # Aplica suavização para a câmera não "pular"
        smoothed_x = int(last_center_x + (current_center - last_center_x) * smoothing_factor)
        
        # Garante que o corte não saia da tela
        # Margem esquerda mínima: metade da largura do crop
        half_crop = target_width // 2
        smoothed_x = max(half_crop, min(smoothed_x, width - half_crop))
        
        centers.append(smoothed_x)
        last_center_x = smoothed_x

    cap.release()
    
    # Se não processou nada (erro grave), devolve lista com centro padrão
    if not centers:
        return [default_center_x] * total_frames_to_scan

    return centers