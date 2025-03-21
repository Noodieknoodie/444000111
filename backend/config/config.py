# backend/config/config.py
import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel

# [MODERN]: Use Pydantic for configuration management
# Provides type validation and better error messages
class AppConfig(BaseModel):
    # Application mode
    APP_MODE: Literal["home", "office", "auto"] = os.environ.get("APP_MODE", "auto").lower()
    
    # Application metadata
    APP_NAME: str = "HohimerPro - 401K Payments"
    APP_VERSION: str = "1.0"
    
    # Base paths depend on the current user
    USERNAME: str = os.getlogin()
    
    # CORS origins
    ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:6069",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:6069",
    ]
    
    # Path configurations
    @property
    def BASE_PATH(self) -> Path:
        return Path(f"C:/Users/{self.USERNAME}/Hohimer Wealth Management/Hohimer Company Portal - Company/Hohimer Team Shared 4-15-19")
    
    @property
    def LOCAL_DB_PATH(self) -> Path:
        return Path(__file__).parent.parent / "data" / "401k_payments.db"
    
    @property
    def OFFICE_DB_PATH(self) -> Path:
        return self.BASE_PATH / "HohimerPro" / "database" / "401k_payments.db"
    
    @property
    def DB_PATH(self) -> Path:
        """Determine database path based on mode and availability"""
        if self.APP_MODE == "home":
            return self.LOCAL_DB_PATH
        elif self.APP_MODE == "office":
            return self.OFFICE_DB_PATH
        else:  # Auto-detect based on file availability
            if self.OFFICE_DB_PATH.exists():
                print("Auto-detected OFFICE mode - using OneDrive database")
                return self.OFFICE_DB_PATH
            else:
                print("Auto-detected HOME mode - using local database")
                return self.LOCAL_DB_PATH
    
    @property
    def DB_BACKUP_PATH(self) -> Path:
        if self.APP_MODE == "office":
            return self.BASE_PATH / "HohimerPro" / "database" / "db_backups"
        else:
            return Path(__file__).parent.parent / "data" / "backup_dbs"
    
    @property
    def PATHS(self) -> dict:
        return {
            'BASE_PATH': self.BASE_PATH,
            'DB_PATH': self.DB_PATH,
            'DB_BACKUP_PATH': self.DB_BACKUP_PATH,
            'APP_MODE': self.APP_MODE,
        }

# Create global configuration instance
settings = AppConfig()

# Validate database path to provide early feedback
from helpers.user_utils import validate_db_path

try:
    validate_db_path(settings.DB_PATH)
    print(f"Successfully connected to database at: {settings.DB_PATH}")
    print(f"Running in {settings.APP_MODE.upper()} mode")
except (FileNotFoundError, Exception) as e:
    print(f"ERROR: {str(e)}")
    print(f"Failed to access database at: {settings.DB_PATH}")
    # If in auto mode and first attempt failed, try the alternative
    if settings.APP_MODE == "auto":
        try:
            alt_path = settings.LOCAL_DB_PATH if settings.DB_PATH == settings.OFFICE_DB_PATH else settings.OFFICE_DB_PATH
            alt_mode = "home" if settings.DB_PATH == settings.OFFICE_DB_PATH else "office"
            print(f"Attempting to use {alt_mode} database instead...")
            validate_db_path(alt_path)
            # Update the path if alternate path works
            settings = AppConfig(APP_MODE=alt_mode)
            print(f"Successfully connected to database at: {settings.DB_PATH}")
            print(f"Running in {settings.APP_MODE.upper()} mode")
        except (FileNotFoundError, Exception) as e2:
            print(f"ERROR: {str(e2)}")
            print("Unable to connect to either office or home database")