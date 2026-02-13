from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MAX_SLOTS: int = 10
    MAX_ITEMS_PER_SLOT: int = 10
    SUPPORTED_DENOMINATIONS: list[int] = [1, 2, 5, 10, 20, 50, 100]
    CURRENCY: str = "INR"
    DATABASE_URL: str = "sqlite:///./vending.db"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
    