from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Defines runtime configuration loaded from environment variables.

    Attributes:
        app_name (str): Human-readable backend name.
        allowed_origins (str): Comma-separated CORS origin list.
        roberta_model_name_or_path (str): Hugging Face model ID or local path.
        google_api_key (str): Google Programmable Search API key.
        google_cse_id (str): Google Programmable Search Engine ID.
        ipfs_api_url (str): IPFS pinning API URL.
        ipfs_api_key (str): IPFS pinning API credential.
        web3_provider_url (str): EVM testnet RPC URL.
        web3_private_key (str): EVM signing private key.
        web3_chain_id (int): EVM chain ID.
        proof_contract_address (str): Optional proof smart contract address.
    """

    app_name: str = "Fake News Detection API"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    roberta_model_name_or_path: str = ""
    google_api_key: str = ""
    google_cse_id: str = ""
    ipfs_api_url: str = ""
    ipfs_api_key: str = ""
    web3_provider_url: str = ""
    web3_private_key: str = ""
    web3_chain_id: int = 0
    proof_contract_address: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        """
        Parses configured CORS origins into a FastAPI-compatible list.

        Returns:
            list[str]: Allowed CORS origins.
        """
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """
    Returns cached application settings.

    Returns:
        Settings: Loaded runtime settings.
    """
    return Settings()
