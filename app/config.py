from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # ---------------------------------------------------------
    # ClickPesa
    # ---------------------------------------------------------

    clickpesa_client_id: str = ""
    clickpesa_api_key: str = ""
    clickpesa_base_url: str = "https://api.clickpesa.com"

    clickpesa_checksum_key: str | None = None

    # Keep TRUE while developing.
    mock_payments: bool = True

    # ---------------------------------------------------------
    # MikroTik RouterOS API
    # ---------------------------------------------------------

    mikrotik_host: str = "192.168.1.59"
    mikrotik_port: int = 8728
    mikrotik_username: str = ""
    mikrotik_password: str = ""
    mikrotik_hotspot_server: str = "hotspot1-server"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()