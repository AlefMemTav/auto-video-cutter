import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Caminhos Base
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    JOBS_DIR: Path = STORAGE_DIR / "jobs"
    
    # Configurações do Whisper
    WHISPER_MODEL: str = "small" # small, medium, large-v2
    WHISPER_DEVICE: str = "cuda"   # "cuda" se tiver NVIDIA, "cpu" se não
    WHISPER_COMPUTE_TYPE: str = "int8"  # float16, int8_float16, int8
    
    # Configurações de Fila
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # Feature Flags
    ENABLE_LLM: bool = False

    class Config:
        env_file = ".env"

    def get_job_path(self, job_id: str) -> Path:
        """Retorna o caminho da pasta de um job específico, criando se não existir."""
        path = self.JOBS_DIR / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

settings = Settings()