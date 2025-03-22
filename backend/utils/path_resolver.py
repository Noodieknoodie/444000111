# backend/utils/path_resolver.py
import os
from datetime import datetime
from typing import Optional
from config import settings
import logging
import win32com.client
import pythoncom
import re

class PathResolver:
    """
    Resolves file paths for the document management system.
    Implements the "Store Once, Link Everywhere" pattern.
    """
    def __init__(self, test_mode=False):
        """Initialize the path resolver with appropriate settings"""
        self.username = os.getlogin()
        self.test_mode = test_mode
        
    def get_mail_dump_path(self, year=None) -> str:
        """
        Resolves the mail dump path with current variables
        
        Args:
            year: Optional year override, defaults to current year
            
        Returns:
            Fully resolved mail dump path
        """
        if year is None:
            year = datetime.now().year
            
        mail_dump = settings.config["files"]["mail_dump"]
        return mail_dump.replace("{username}", self.username).replace("{year}", str(year))
    
    def get_client_folder_path(self, client_name: str) -> str:
        """
        Resolves a specific client folder path
        
        Args:
            client_name: Client display name
            
        Returns:
            Fully resolved client folder path
        """
        base_path = settings.config["files"]["client_base"]
        base_path = base_path.replace("{username}", self.username)
        return os.path.join(base_path, client_name)
    
    def get_shortcut_path(self, client_name: str, file_name: str, year: int) -> str:
        """
        Gets path where a shortcut should be placed
        
        Args:
            client_name: Client display name
            file_name: Name of the file (shortcut will append .lnk)
            year: Year for subfolder organization
            
        Returns:
            Fully resolved path for the shortcut file
        """
        client_path = self.get_client_folder_path(client_name)
        return os.path.join(client_path, "Consulting Fee", str(year), file_name + ".lnk")
    
    def create_windows_shortcut(self, target_path: str, shortcut_path: str) -> bool:
        """
        Creates a Windows shortcut (.lnk file) pointing to the target
        
        Args:
            target_path: Path to the original file
            shortcut_path: Path where shortcut should be created
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
            
            # Initialize COM objects for shortcut creation
            pythoncom.CoInitialize()
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = target_path
            shortcut.save()
            
            logging.info(f"Created shortcut: {shortcut_path} -> {target_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to create shortcut: {str(e)}")
            return False
    
    def extract_year_from_filename(self, filename: str) -> Optional[int]:
        """
        Extracts year from a filename containing a date
        
        Args:
            filename: Name of the file
            
        Returns:
            Year as integer or None if not found
        """
        # Look for date patterns like MM.DD.YY or MM.DD.YYYY
        date_patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})',  # MM.DD.YY or MM.DD.YYYY
            r'Q[1-4]-(\d{2,4})',                 # Q1-YY or Q1-YYYY
            r'rcvd .*?(\d{1,2})\.(\d{1,2})\.(\d{2,4})'  # rcvd MM.DD.YY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                # If it's MM.DD.YY pattern
                if len(match.groups()) == 3:
                    year_str = match.group(3)
                    # Handle 2-digit years
                    if len(year_str) == 2:
                        year = int(year_str)
                        # Assume 20xx for years less than 50
                        if year < 50:
                            return 2000 + year
                        else:
                            return 1900 + year
                    return int(year_str)
                # If it's Q1-YY pattern
                else:
                    year_str = match.group(1)
                    if len(year_str) == 2:
                        year = int(year_str)
                        if year < 50:
                            return 2000 + year
                        else:
                            return 1900 + year
                    return int(year_str)
        
        # Default to current year if no date found
        return datetime.now().year
