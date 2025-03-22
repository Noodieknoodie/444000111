# backend/utils/file_manager.py
import os
import shutil
import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import settings
from database import get_db_connection
from utils.path_resolver import PathResolver

class FileManager:
    def __init__(self, test_mode=False):
        """Initialize the file manager with appropriate base paths"""
        self.base_path = settings.get_files_base_path(is_test=test_mode)
        self.path_resolver = PathResolver(test_mode=test_mode)
        self.test_mode = test_mode
        
    def get_full_path(self, relative_path: str) -> str:
        """Convert a relative path to a full OneDrive path"""
        if not relative_path:
            return None
            
        base = self.base_path
        # Replace username in path if needed
        if "{username}" in base:
            base = base.replace("{username}", os.getlogin())
            
        return os.path.join(base, relative_path)
        
    def get_client_folder(self, client_id: int) -> Optional[str]:
        """Get the client folder name from the database"""
        conn = get_db_connection(test_mode=self.test_mode)
        try:
            client = conn.execute(
                "SELECT display_name FROM clients WHERE client_id = ? AND valid_to IS NULL", 
                (client_id,)
            ).fetchone()
            
            if not client:
                logging.error(f"Client ID {client_id} not found")
                return None
                
            return client['display_name']
        finally:
            conn.close()
    
    def create_client_file_path(self, client_id: int, filename: str) -> Dict:
        """
        Create a standardized file path for client documents and record in database
        
        Returns:
            Dict with file_id and full_path
        """
        client_folder = self.get_client_folder(client_id)
        if not client_folder:
            raise ValueError(f"Client ID {client_id} not found")
            
        # Generate path structure: ClientName/Consulting Fee/YYYY/filename
        year = datetime.now().strftime("%Y")
        relative_path = f"{client_folder}/Consulting Fee/{year}/{filename}"
        
        # Ensure directory exists
        full_path = self.get_full_path(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Store in database
        conn = get_db_connection(test_mode=self.test_mode)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO client_files(client_id, file_name, onedrive_path, uploaded_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (client_id, filename, relative_path)
                )
                file_id = cursor.lastrowid
                
            return {"file_id": file_id, "full_path": full_path}
        finally:
            conn.close()
    
    def save_document_to_mail_dump(self, file_obj, filename: str, document_date: Optional[str] = None, provider_id: Optional[int] = None) -> Dict:
        """
        Save a document to the mail dump folder following the "Store Once" principle
        
        Args:
            file_obj: UploadFile object
            filename: Original filename
            document_date: Optional date of the document (extracted from filename or provided)
            provider_id: Optional provider ID
            
        Returns:
            Dict with file_id and path information
        """
        # Extract year from filename or use current year
        year = self.path_resolver.extract_year_from_filename(filename)
        
        # Get mail dump path for this year
        mail_dump_path = self.path_resolver.get_mail_dump_path(year)
        
        # Ensure directory exists
        os.makedirs(mail_dump_path, exist_ok=True)
        
        # Create the full path to save the file
        file_path = os.path.join(mail_dump_path, filename)
        
        # Save file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file_obj.file, buffer)
        
        # If no document date provided, use today
        if not document_date:
            document_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create database entry
        conn = get_db_connection(test_mode=self.test_mode)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO client_files(file_path, original_filename, upload_date, document_date, provider_id, is_processed) 
                       VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, 0)""",
                    (file_path, filename, document_date, provider_id)
                )
                file_id = cursor.lastrowid
                
            return {"file_id": file_id, "file_path": file_path}
        finally:
            conn.close()
    
    def save_uploaded_file(self, client_id: int, file_obj, filename: str, provider_id: Optional[int] = None) -> Dict:
        """
        Save an uploaded file using the "Store Once, Link Everywhere" pattern
        
        Args:
            client_id: Client ID (for linking)
            file_obj: UploadFile object
            filename: Name to save the file as
            provider_id: Optional provider ID
            
        Returns:
            Dict with file_id and path information
        """
        # First save to mail dump to implement "Store Once"
        result = self.save_document_to_mail_dump(file_obj, filename, provider_id=provider_id)
        file_id = result["file_id"]
        file_path = result["file_path"]
        
        # Get client name for shortcut creation
        client_name = self.get_client_folder(client_id)
        if not client_name:
            raise ValueError(f"Client ID {client_id} not found")
        
        # Extract year from filename for shortcut folder
        year = self.path_resolver.extract_year_from_filename(filename)
        
        # Create shortcut to implement "Link Everywhere"
        shortcut_path = self.path_resolver.get_shortcut_path(client_name, filename, year)
        self.path_resolver.create_windows_shortcut(file_path, shortcut_path)
        
        # Mark as processed since we've created the shortcut
        conn = get_db_connection(test_mode=self.test_mode)
        try:
            with conn:
                conn.execute(
                    "UPDATE client_files SET is_processed = 1 WHERE file_id = ?",
                    (file_id,)
                )
        finally:
            conn.close()
            
        return {"file_id": file_id, "file_path": file_path}
    
    def link_file_to_payment(self, file_id: int, payment_id: int) -> bool:
        """Link a file to a payment record"""
        conn = get_db_connection(test_mode=self.test_mode)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO payment_files(payment_id, file_id, linked_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (payment_id, file_id)
                )
            return True
        except Exception as e:
            logging.error(f"Failed to link file {file_id} to payment {payment_id}: {str(e)}")
            return False
        finally:
            conn.close()
    
    def get_file_info(self, file_id: int) -> Optional[Dict]:
        """Get file information from database"""
        conn = get_db_connection(test_mode=self.test_mode)
        try:
            result = conn.execute(
                """
                SELECT cf.file_id, cf.client_id, cf.file_name, cf.onedrive_path, cf.uploaded_at
                FROM client_files cf
                WHERE cf.file_id = ?
                """,
                (file_id,)
            ).fetchone()
            
            if not result:
                return None
                
            return dict(result)
        finally:
            conn.close()
