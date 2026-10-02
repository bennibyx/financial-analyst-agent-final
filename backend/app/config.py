import os

from dotenv import load_dotenv

# Loads variables from a .env file (never committed) into the environment.
load_dotenv()


class Settings:
    # Nebius Token Factory (LLM inference). Copy the exact base URL and model
    # name from the Token Factory docs/console; do not guess them.
    nebius_api_key: str = os.getenv("NEBIUS_API_KEY", "")
    nebius_base_url: str = os.getenv("NEBIUS_BASE_URL", "")
    model_name: str = os.getenv("MODEL_NAME", "")

    # Storage
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "20"))

    # Frontend origin allowed by CORS (used from Day 16)
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:8501")


settings = Settings()
