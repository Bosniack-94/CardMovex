from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Configuración global del sistema CardMovex.
    Pydantic V2 carga automáticamente las variables desde el archivo .env.
    No se necesita os.getenv ni importar dotenv manualmente.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False  # OPENAI_API_KEY == openai_api_key
    )

    # === OpenAI ===
    OPENAI_API_KEY: str  # Requerido: falla al iniciar si no está definido en .env

    # === Gemini (Fallback) ===
    GEMINI_API_KEY: str | None = None


    # === Motor de IA ===
    DEFAULT_LLM_MODEL: str = "gpt-4o-mini"

    # === Sistema de Autonomía ===
    # Movimientos con score menor a este threshold → needs_review = True
    CONFIDENCE_THRESHOLD: float = 0.85

    # === Belvo API ===
    BELVO_SECRET_ID: str
    BELVO_SECRET_PASSWORD: str
    BELVO_ENVIRONMENT: str = "sandbox"

# Singleton de configuración: se importa en toda la app con `from config.settings import settings`
settings = Settings()
