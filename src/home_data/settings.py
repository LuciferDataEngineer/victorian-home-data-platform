from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "dev"
    data_root: Path = Path("data")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HOME_DATA_",
        extra="ignore",
    )

    @property
    def bronze_root(self) -> Path:
        return self.data_root / "bronze"

    @property
    def silver_root(self) -> Path:
        return self.data_root / "silver"

    @property
    def gold_root(self) -> Path:
        return self.data_root / "gold"

