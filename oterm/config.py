import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class AppConfig(BaseModel):
    ENV: str = "development"
    OLLAMA_URL: str = "http://localhost:11434/api"


# Expose Config object for app to import
Config = AppConfig.model_validate(os.environ)
