from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Documents a user must agree to before surveying (SEC-CON-01).
# Bump a version to require re-consent (SEC-CON-02).
CONSENT_VERSIONS = {"terms": "1", "privacy": "1", "research": "1"}

ITEM_SET_VERSION = "0.1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    supabase_url: str = ""
    jwt_audience: str = "authenticated"
    allowed_origins: str = "http://localhost:5173"
    models_dir: Path = Path(__file__).resolve().parent.parent / "models"

    # Emergency Mode (NFR-AVL-03)
    emergency_level: int = 0
    signup_enabled: bool = True
    survey_write_enabled: bool = True
    read_only_mode: bool = False

    log_salt: str = "dev"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def writes_enabled(self) -> bool:
        return self.survey_write_enabled and not self.read_only_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
