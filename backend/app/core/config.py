from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SwasthAI"
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "swasthai_db"
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
