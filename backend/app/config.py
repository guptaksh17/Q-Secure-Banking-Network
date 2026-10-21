"""Application configuration.

All settings come from environment variables (prefix ``QSB_``) or ``backend/.env``.
Validation happens once at startup so a bad threshold or sample fraction fails
loudly instead of silently corrupting a QKD session later.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QSB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Q-Secure Banking Network"
    environment: Literal["development", "test", "production"] = "development"

    # NoDecode: accept a plain comma-separated string instead of requiring JSON.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    database_url: str = "sqlite:///./qsb.db"

    # --- QKD defaults ---
    # Illustrative abort threshold; strictly between 0 and 0.5 (QBER 0.5 = no correlation).
    qber_threshold: float = Field(default=0.11, gt=0.0, lt=0.5)
    # Fraction of sifted bits disclosed for QBER estimation and then discarded.
    qber_sample_fraction: float = Field(default=0.25, gt=0.0, lt=1.0)
    default_qubits: int = Field(default=4096, ge=16, le=200_000)
    quantum_backend: Literal["numpy", "qiskit"] = "numpy"
    random_seed: int | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("random_seed", mode="before")
    @classmethod
    def _empty_seed_is_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance; tests clear the cache to apply overrides."""
    return Settings()
