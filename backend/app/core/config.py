from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SwasthAI"
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "swasthai_db"
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    # Free-tier Google AI Studio key (aistudio.google.com/apikey) for the
    # report analyzer's plain-language explanation step. Optional: left
    # empty, that step is skipped and the rule-based summary is still
    # returned on its own (see app/ai/inference/report_explanation.py).
    GEMINI_API_KEY: str = ""

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
