import cv2
import mediapipe as mp
import logging

logger = logging.getLogger(__name__)

def get_smart_crop_x(video_path: str, start_time: float, duration: float, target_w=1080, target_h=1920) -> int:
    """
    Analisa o frame central do segmento e retorna a coordenada X para o corte (crop).
    Retorna None se não achar rosto (para usar fallback centralizado).
    """
    try:
        mp_face_detection = mp.solutions.face_detection
        
        # Abre o vídeo
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning("Não foi possível abrir o vídeo para Smart Crop.")
            return None

        # Pula para o meio do clipe para ter uma boa amostra
        middle_time = start_time + (duration / 2)
        # Define a posição em milissegundos
        cap.set(cv2.CAP_PROP_POS_MSEC, middle_time * 1000)
        
        success, image = cap.read()
        if not success:
            logger.warning("Falha ao ler frame para Smart Crop.")
            cap.release()
            return None

        img_h, img_w, _ = image.shape
        
        # Inicializa o Detector de Face
        with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
            # Converte para RGB (MediaPipe usa RGB, OpenCV usa BGR)
            results = face_detection.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            if not results.detections:
                logger.info("Nenhum rosto detectado no frame central. Usando centro padrão.")
                cap.release()
                return None

            # Pega o primeiro rosto (ou o mais confiável)
            # O MediaPipe retorna bounding box relativa (0.0 a 1.0)
            detection = results.detections[0]
            bbox = detection.location_data.relative_bounding_box
            
            # Centro do rosto (0.0 a 1.0)
            face_center_x_rel = bbox.xmin + (bbox.width / 2)
            
            # --- CÁLCULO DO CROP ---
            # O vídeo será escalado para ter altura 1920.
            # Qual será a largura escalada?
            # Se original é 1920x1080 (16:9), ao escalar altura pra 1920:
            scale_factor = target_h / img_h
            scaled_w = int(img_w * scale_factor)
            
            # Onde está o centro do rosto na imagem escalada (em pixels)?
            face_center_x_px = int(face_center_x_rel * scaled_w)
            
            # Queremos que esse ponto seja o centro do nosso crop de 1080px
            # X_inicial = Centro_Rosto - (Metade_da_Largura_Do_Crop)
            crop_x = face_center_x_px - (target_w // 2)
            
            # Correção de Limites (Não pode sair da tela)
            # Não pode ser menor que 0
            if crop_x < 0: crop_x = 0
            # Não pode ser maior que (Largura_Total - Largura_Crop)
            if crop_x > (scaled_w - target_w): crop_x = scaled_w - target_w
            
            logger.info(f"Smart Crop: Rosto em {face_center_x_rel:.2f}. Crop X calculado: {crop_x}")
            
            cap.release()
            return crop_x

    except Exception as e:
        logger.error(f"Erro no Smart Crop: {e}")
        return None