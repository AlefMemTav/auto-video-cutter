import sys
from app.config.queue import video_queue
from app.jobs.worker import process_video_pipeline

def main():
    if len(sys.argv) < 2:
        print("Uso: python main.py <URL_DO_YOUTUBE>")
        return

    url = sys.argv[1]
    
    print("\n📩 AUTO VIDEO CUTTER (Modo Assíncrono)")
    print("=======================================")
    
    # Em vez de chamar a função direto, "enfileiramos" (enqueue)
    # timeout='1h' dá 1 hora para o worker processar antes de dar erro
    job = video_queue.enqueue(
        process_video_pipeline, 
        url, 
        job_timeout='1h' 
    )

    print(f"✅ Job enviado para a fila!")
    print(f"🆔 ID do Job: {job.get_id()}")
    print(f"📊 Status: {job.get_status()}")
    print("\nO Worker está processando em segundo plano.")
    print("Você pode enviar outro vídeo agora mesmo!")

if __name__ == "__main__":
    main()