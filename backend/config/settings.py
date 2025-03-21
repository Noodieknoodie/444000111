# backend/config/settings.py
import os
import yaml
import logging
from pathlib import Path

class Settings:
    def __init__(self):
        self.config = self._load_config()
        
    def _load_config(self):
        """Load configuration from YAML file"""
        config_path = Path(__file__).parent.parent / "config.yaml"
        
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logging.warning(f"Config file not found at {config_path}. Using default values.")
            return self._default_config()
    
    def _default_config(self):
        """Provide default configuration if file not found"""
        return {
            "database": {
                "home": "backend/data/401k_payments_66.db",
                "test": "backend/data/401k_payments_test.db",
                "fallback": "backend/data/401k_payments_master.db",
                "backup": {
                    "home": "backend/data/backup_dbs"
                }
            },
            "files": {
                "base_path": "backend/data/files",
                "test_path": "backend/data/test_files"
            }
        }
    
    def get_db_paths(self):
        """Return database paths with username replaced"""
        username = os.getlogin()
        
        paths = []
        if "office" in self.config["database"]:
            paths.append(self.config["database"]["office"].replace("{username}", username))
        
        paths.append(self.config["database"]["home"])
        paths.append(self.config["database"]["fallback"])
        
        return [path for path in paths if path]
    
    def get_test_db_path(self):
        """Return test database path"""
        return self.config["database"]["test"]
    
    def get_files_base_path(self, is_test=False):
        """Return file storage base path with username replaced"""
        if is_test:
            return self.config["files"]["test_path"]
        
        username = os.getlogin()
        return self.config["files"]["base_path"].replace("{username}", username)
    
    def get_backup_path(self):
        """Return backup directory path with username replaced"""
        username = os.getlogin()
        
        if "office" in self.config["database"]["backup"]:
            office_path = self.config["database"]["backup"]["office"].replace("{username}", username)
            if os.path.exists(os.path.dirname(office_path)):
                return office_path
        
        return self.config["database"]["backup"]["home"]

settings = Settings()