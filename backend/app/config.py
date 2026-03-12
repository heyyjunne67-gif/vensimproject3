from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MODEL_PATH: str = "./models/model_hongoroo.py"
    SIM_TIME_STEP: float = 1.0
    DYNAMIC_SLIDER_LIMIT: int = 24

    # ===== OpenAI =====
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_CHAT_PATH: str = "/chat/completions"

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    # Allow local network dev URLs like http://192.168.x.x:5173 or 5174
    ALLOWED_ORIGIN_REGEX: str = r"^http://(localhost|127\\.0\\.0\\.1|192\\.168\\.\d+\\.\d+):(5173|5174)$"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [s.strip() for s in self.ALLOWED_ORIGINS.split(",") if s.strip()]

    @property
    def allowed_origin_regex(self) -> str | None:
        value = (self.ALLOWED_ORIGIN_REGEX or "").strip()
        return value or None


settings = Settings()


