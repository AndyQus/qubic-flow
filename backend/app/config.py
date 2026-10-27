from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # "production" (Docker/Umbrel default) or "development" (local dev via
    # launch.json/tasks.json) — controls feature defaults like the balance
    # history capture series (off in prod, on in dev for testing)
    app_env: str = "production"
    database_url: str = "sqlite:////app/data/qubicflow.db"
    qubic_rpc_url: str = "https://rpc.qubic.org"
    qx_api_url: str = "https://qxinfo.qubic.org/api"  # official QX API (qubic/qx-service)
    coingecko_api_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str = ""
    cors_origins: str = "http://localhost:8080,http://localhost:5173"
    log_level: str = "INFO"
    # Budget for public Qubic APIs (rpc.qubic.org, public BOB nodes). Cloudflare
    # limits per public IP (~100-120/min) and that budget is shared with every
    # device in the network (Home Node, browser wallet, explorer). Own nodes in
    # the LAN are not throttled.
    public_rpc_rate_limit_per_min: int = 25
    public_rpc_burst: int = 5
    app_password: str = ""  # Injected by Umbrel as APP_PASSWORD; if set, protects backup endpoints

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
