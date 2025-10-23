"""
Centralized configuration management for RyzeAgent Backend
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


class GoogleAdsConfig:
    """Google Ads API configuration"""
    
    def __init__(self):
        self.developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        self.client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
        self.refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
        self.api_version = os.getenv("GOOGLE_ADS_API_VERSION", "v19")
    
    def validate(self) -> bool:
        """Validate that all required credentials are present"""
        required = [
            self.developer_token,
            self.client_id,
            self.client_secret,
            self.refresh_token
        ]
        return all(required)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Google Ads client"""
        return {
            "developer_token": self.developer_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "use_proto_plus": True,
        }


class DatabaseConfig:
    """Database configuration"""
    
    def __init__(self):
        self.url = os.getenv("DATABASE_URL", "sqlite:///ryzeagent.db")
        self.echo = os.getenv("DATABASE_ECHO", "false").lower() == "true"


class AppConfig:
    """Main application configuration"""
    
    def __init__(self):
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Sub-configs
        self.google_ads = GoogleAdsConfig()
        self.database = DatabaseConfig()
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate all configurations"""
        errors = []
        
        if not self.google_ads.validate():
            errors.append("Google Ads credentials are incomplete")
        
        return len(errors) == 0, errors


# Global config instance
config = AppConfig()
