import os
from uuid import UUID

from dotenv import load_dotenv


load_dotenv()


class Settings:
    LEGACY_COMPANY_ID: str = "00000000-0000-4000-8000-000000000001"
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "sales_predictions")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    STREAMLIT_COMPANY_ID: str = os.getenv(
        "STREAMLIT_COMPANY_ID",
        LEGACY_COMPANY_ID,
    )
    STREAMLIT_USE_RUNTIME_ROLE: bool = os.getenv(
        "STREAMLIT_USE_RUNTIME_ROLE",
        "false",
    ).lower() in {"1", "true", "yes"}

    @property
    def company_id(self) -> str:
        try:
            return str(UUID(self.STREAMLIT_COMPANY_ID))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "STREAMLIT_COMPANY_ID doit contenir l'UUID d'un dépôt autorisé."
            ) from exc

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgres://"):
                return self.DATABASE_URL.replace(
                    "postgres://",
                    "postgresql+psycopg://",
                    1,
                )
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace(
                    "postgresql://",
                    "postgresql+psycopg://",
                    1,
                )
            return self.DATABASE_URL
        return (
            "postgresql+psycopg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
