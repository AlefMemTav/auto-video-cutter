import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # --- CAMINHOS DINÂMICOS ---
    # O arquivo settings.py está em: /app/app/config/settings.py
    # .parent        -> /app/app/config
    # .parent.parent -> /app/app
    # .parent.parent.parent -> /app (A Raiz do Projeto no Docker)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # Define a pasta storage na raiz (irmã da pasta app)
    # Resultado final: /app/storage
    STORAGE_DIR: Path = BASE_DIR / "storage"
    
    # Resultado final: /app/storage/jobs
    JOBS_DIR: Path = STORAGE_DIR / "jobs"
    
    # --- WHISPER ---
    WHISPER_MODEL: str = "small" # small, medium, large-v2
    WHISPER_DEVICE: str = "cuda"   # "cuda" se tiver NVIDIA, "cpu" se não
    WHISPER_COMPUTE_TYPE: str = "int8"  # float16, int8_float16, int8
    
    # --- REDIS ---
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = 6379
    
    ENABLE_LLM: bool = False

    class Config:
        env_file = ".env"

    def get_job_path(self, job_id: str) -> Path:
        """
        Cria e retorna o caminho ABSOLUTO para um job.
        Ex: /app/storage/jobs/uuid-do-job
        """
        path = self.JOBS_DIR / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

settings = Settings()