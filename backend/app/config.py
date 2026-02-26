"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    debug: bool = False
    secret_key: str = "change-this-in-production"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_pass: str = "postgres"
    db_name: str = "ai_sales_agent"
    database_url: Optional[str] = None
    
    @property
    def get_database_url(self) -> str:
        """Get the database URL, either from environment or constructed from components."""
        if self.database_url:
            return self.database_url
        url = f"postgresql+asyncpg://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"
        # Aiven and some other cloud providers require SSL
        if "aivencloud.com" in self.db_host:
            url += "?ssl=require"
        return url
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_user: Optional[str] = "default"
    redis_password: Optional[str] = None
    redis_url: Optional[str] = None
    
    @property
    def get_redis_url(self) -> str:
        """Get the Redis URL, either from environment or constructed from components."""
        if self.redis_url:
            return self.redis_url
        
        user_pass = ""
        if self.redis_password:
            user_pass = f"{self.redis_user or 'default'}:{self.redis_password}@"
        elif self.redis_user and self.redis_user != "default":
            user_pass = f"{self.redis_user}@"
            
        return f"redis://{user_pass}{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    # Azure OpenAI
    azure_ai_endpoint: str = "https://anndocextopenai.cognitiveservices.azure.com/"
    azure_ai_api_key: str = ""
    gpt_4_1_deployment: str = "gpt-4.1"
    gpt_4_1_mini_deployment: str = "gpt-4.1-mini"
    # Which deployment to use by default
    azure_openai_deployment: str = "gpt-4.1"
    
    # Resend
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"
    resend_from_name: str = "xendex"
    resend_reply_to: Optional[str] = None
    
    # PhantomBuster / LinkedIn Cookie  
    phantombuster_api_key: str = ""
    phantombuster_linkedin_phantom_id: str = ""
    phantombuster_li_at: str = ""  # LinkedIn li_at session cookie
    linkedin_li_at: str = ""  # Direct LinkedIn cookie (alternative to phantombuster_li_at)
    
    @property
    def linkedin_cookie(self) -> str:
        """Get the LinkedIn li_at cookie from any available source."""
        return self.linkedin_li_at or self.phantombuster_li_at or ""
    
    # Google Custom Search API (fallback)
    google_api_key: str = ""
    google_search_engine_id: str = ""
    
    # SerpAPI (primary search provider - get free key at serpapi.com)
    serpapi_key: str = ""
    
    # Your Company
    your_website_url: str = ""
    
    # Compliance
    data_retention_days: int = 365
    unsubscribe_url: str = ""
    
    # Lead Qualification
    qualification_threshold: float = 0.40  # 40% per dimension to qualify
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL for Alembic."""
        return self.get_database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
