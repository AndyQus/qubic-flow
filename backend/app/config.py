from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "sqlite:////app/data/qubicflow.db"
    qubic_rpc_url: str = "https://rpc.qubic.org"
    qx_api_url: str = "https://qxinfo.qubic.org/api"  # official QX API (qubic/qx-service)
    coingecko_api_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str = ""
    cors_origins: str = "http://localhost:8080,http://localhost:5173"
    log_level: str = "INFO"
    app_password: str = ""  # Injected by Umbrel as APP_PASSWORD; if set, protects backup endpoints

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
