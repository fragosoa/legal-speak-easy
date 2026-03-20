from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 4096
    app_env: str = "development"
    max_file_size_mb: int = 10
    contract_text_max_chars: int = 80000
    secret_key: str
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = {"env_file": ".env"}


settings = Settings()


def get_settings() -> Settings:
    return settings
