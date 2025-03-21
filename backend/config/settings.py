# backend/config/settings.py
import os
import yaml
import logging
from pathlib import Path

class Settings:
    def __init__(self):
        self.config = self._load_config()
        self.base_dir = self._get_base_dir()
        
    def _get_base_dir(self):
        """Determine the base directory for relative paths"""
        # If current directory ends with 'backend', we're already in the backend folder
        cwd = os.getcwd()
        if os.path.basename(cwd) == "backend":
            return ""
        else:
            return "backend"  # Prefix relative paths with 'backend/'
        
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
                "home": "data/401k_payments_66.db",
                "test": "data/401k_payments_test.db",
                "fallback": "data/401k_payments_master.db",
                "backup": {
                    "home": "data/backup_dbs"
                }
            },
            "files": {
                "base_path": "data/files",
                "test_path": "data/test_files"
            }
        }
    
    def _fix_path(self, path):
        """Fix relative paths by prefixing with base_dir if needed"""
        if path and not os.path.isabs(path) and not path.startswith(self.base_dir):
            # Only add 'backend/' prefix for relative paths not already prefixed
            if 'backend/' in path and not path.startswith('backend/'):
                # Path contains 'backend/' but not at the start, don't modify
                return path
            elif path.startswith('backend/') and self.base_dir == 'backend':
                # Avoid double 'backend/backend/' prefix
                return path
            else:
                return os.path.join(self.base_dir, path)
        return path
    
    def get_db_paths(self):
        """Return database paths with username replaced"""
        username = os.getlogin()
        
        paths = []
        if "office" in self.config["database"]:
            office_path = self.config["database"]["office"].replace("{username}", username)
            paths.append(office_path)
        
        # Fix relative paths
        home_path = self._fix_path(self.config["database"]["home"])
        fallback_path = self._fix_path(self.config["database"]["fallback"])
        
        paths.append(home_path)
        paths.append(fallback_path)
        
        return [path for path in paths if path]
    
    def get_test_db_path(self):
        """Return test database path"""
        return self._fix_path(self.config["database"]["test"])
    
    def get_files_base_path(self, is_test=False):
        """Return file storage base path with username replaced"""
        if is_test:
            return self._fix_path(self.config["files"]["test_path"])
        
        username = os.getlogin()
        if "base_path" in self.config["files"] and "{username}" in self.config["files"]["base_path"]:
            return self.config["files"]["base_path"].replace("{username}", username)
        else:
            return self._fix_path(self.config["files"]["base_path"])
    
    def get_backup_path(self):
        """Return backup directory path with username replaced"""
        username = os.getlogin()
        
        if "office" in self.config["database"]["backup"]:
            office_path = self.config["database"]["backup"]["office"].replace("{username}", username)
            if os.path.exists(os.path.dirname(office_path)):
                return office_path
        
        return self._fix_path(self.config["database"]["backup"]["home"])

settings = Settings()