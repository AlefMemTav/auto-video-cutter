import sys
from app.jobs.worker import process_video_pipeline

def main():
    if len(sys.argv) < 2:
        print("Uso: python main.py <URL_DO_YOUTUBE>")
        return

    url = sys.argv[1]
    
    print("\n🎬 AUTO VIDEO CUTTER v1.0")
    print("=========================")
    print(f"Processando: {url}")
    print("Aguarde... isso vai usar 100% da sua CPU.\n")

    try:
        process_video_pipeline(url)
    except KeyboardInterrupt:
        print("\n🛑 Processo interrompido pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro: {e}")

if __name__ == "__main__":
    main()