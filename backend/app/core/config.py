from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SwasthAI"
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "swasthai_db"

    class Config:
        env_file = ".env"

settings = Settings()
