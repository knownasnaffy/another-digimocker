from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8001
    HOST: str = "0.0.0.0"

    # These must match what the EV backend sends — mock validates them
    CLIENT_ID: str = "mock_client_id"
    CLIENT_SECRET: str = "mock_client_secret"

    # If true, mock enforces PKCE code_challenge/code_verifier validation
    # Set to false for quick manual testing; always true in CI
    ENFORCE_PKCE: bool = True

    # Token lifetimes (seconds)
    ACCESS_TOKEN_EXPIRES_IN: int = 3600
    REFRESH_TOKEN_EXPIRES_IN: int = 86400

    # Path to the personas file
    PERSONAS_FILE: str = "personas.json"

    class Config:
        env_file = ".env"


settings = Settings()
