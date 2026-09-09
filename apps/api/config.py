from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://cortexbi:cortexbi_dev@localhost:5432/cortexbi"
    JWT_SECRET_KEY: str

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def jwt_secret_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("JWT_SECRET_KEY must be set to a non-empty value")
        return v
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60 * 24

    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_ROOT: str = "./var/storage"
    STORAGE_S3_BUCKET: str = ""
    STORAGE_S3_REGION: str = ""

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""

    MAX_UPLOAD_SIZE_MB: int = 200
    MAX_UPLOAD_ROWS: int = 1_000_000
    SAMPLE_ROWS: int = 300_000
    MAX_COLUMNS: int = 100
    SHAP_SAMPLE_SIZE: int = 1_000
    MAX_TOKENS_PER_ANALYSIS: int = 5_000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
