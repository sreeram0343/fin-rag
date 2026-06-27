from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    ENV: Literal["development", "staging", "production"] = "development"
    PROJECT_NAME: str = "FinRAG-Platform"
    LOG_LEVEL: str = "INFO"

    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/finrag",
        description="PostgreSQL connection string"
    )
    VECTOR_DB_URL: str = Field(
        default="http://localhost:6333",
        description="Vector database Qdrant/Pinecone endpoint"
    )
    VECTOR_DB_API_KEY: SecretStr = Field(
        default=SecretStr("mock-vector-db-api-key")
    )

    # Redis & Message Broker Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage Settings
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: SecretStr = Field(default=SecretStr("minioadmin"))
    MINIO_SECURE: bool = False

    # LLM Providers (Strict Zero Data Retention)
    OPENAI_API_KEY: SecretStr = Field(default=SecretStr("mock-openai-key"))
    ANTHROPIC_API_KEY: SecretStr = Field(default=SecretStr("mock-anthropic-key"))

    # Embedding & Chunking Settings
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32
    CHUNK_MAX_TOKENS: int = 512
    CHUNK_OVERLAP_TOKENS: int = 64
    QDRANT_COLLECTION_NAME: str = "finrag_chunks"

    # Security Secrets
    SECRET_KEY: SecretStr = Field(
        default=SecretStr("your-super-secret-cryptographic-signing-key-32-chars-min")
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
