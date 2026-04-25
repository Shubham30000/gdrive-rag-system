"""
config.py
Central configuration – reads from environment / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Google Drive
    google_service_account_file: str = "service_account.json"
    gdrive_folder_id: str = ""          # empty → search all of Drive

    # Gemini
    gemini_api_key: str = ""

    # AI Pipe (https://aipipe.org)
    aipipe_token: str = ""

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Storage
    faiss_index_path: str = "data/faiss.index"
    metadata_path: str = "data/metadata.json"

    # Chunking
    chunk_size: int = 450
    chunk_overlap: int = 75

    # Retrieval
    top_k: int = 5
    min_score: float = 0.25

    def ensure_dirs(self):
        Path(self.faiss_index_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.metadata_path).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
