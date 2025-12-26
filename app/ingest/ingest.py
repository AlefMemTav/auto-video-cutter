import os
import shutil
import logging
import yt_dlp


# Configuração básica de log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ingest_video(source: str, job_folder: str) -> str:
    """
    Decide se baixa do YouTube ou pega um arquivo local.
    Retorna o caminho final do arquivo input.mp4
    """
    output_path = os.path.join(job_folder, "input.mp4")
    
    # --- CENÁRIO 1: É UMA URL (YOUTUBE) ---
    if source.startswith(('http://', 'https://', 'www.')):
        logger.info(f"🌐 Detectada URL. Iniciando download via yt-dlp: {source}")
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            # Otimizações para não baixar thumbnails ou metadados inúteis
            'writethumbnail': False,
            'writeinfojson': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([source])
            return output_path
        except Exception as e:
            logger.error(f"Erro no download do YouTube: {e}")
            raise e

    # --- CENÁRIO 2: É UM ARQUIVO LOCAL ---
    else:
        # No Docker, a raiz do projeto é /app. 
        # Vamos procurar o arquivo na pasta 'inputs' que criamos.
        source_path = os.path.join("/app/inputs", source)
        
        logger.info(f"📂 Detectado arquivo local. Procurando em: {source_path}")
        
        if not os.path.exists(source_path):
            error_msg = f"Arquivo não encontrado na pasta 'inputs': {source}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        # Copia o arquivo para a pasta do Job para processar
        try:
            shutil.copy(source_path, output_path)
            logger.info(f"✅ Arquivo copiado com sucesso para o processamento.")
            return output_path
        except Exception as e:
            logger.error(f"Erro ao copiar arquivo local: {e}")
            raise e