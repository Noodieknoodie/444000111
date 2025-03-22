# backend/utils/document_processor.py
import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import sqlite3
from pathlib import Path
import json

from database import get_db_connection
from utils.path_resolver import PathResolver
from utils.file_manager import FileManager


class DocumentProcessor:
    """
    Processes documents in the mail dump folder, extracting metadata
    and creating appropriate database entries and shortcuts.
    """
    def __init__(self, test_mode=False):
        self.path_resolver = PathResolver(test_mode=test_mode)
        self.file_manager = FileManager(test_mode=test_mode)
        self.test_mode = test_mode
        self.conn = get_db_connection(test_mode=test_mode)
        
    def __del__(self):
        """Close database connection on cleanup"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
    
    def get_document_patterns(self, pattern_type: str) -> List[Dict]:
        """Get document recognition patterns from the database"""
        patterns = self.conn.execute(
            """SELECT pattern_id, pattern, description, priority 
               FROM document_patterns 
               WHERE pattern_type = ? 
               AND is_active = 1
               ORDER BY priority DESC""",
            (pattern_type,)
        ).fetchall()
        
        return [dict(p) for p in patterns]
    
    def is_401k_document(self, filename: str) -> bool:
        """Check if a file is a 401k payment document based on patterns"""
        doc_type_patterns = self.get_document_patterns('document_type')
        
        for pattern_dict in doc_type_patterns:
            pattern = pattern_dict['pattern']
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        
        return False
    
    def extract_provider_name(self, filename: str) -> Optional[str]:
        """Extract provider name from filename using patterns"""
        provider_patterns = self.get_document_patterns('provider_pattern')
        
        for pattern_dict in provider_patterns:
            pattern = pattern_dict['pattern']
            match = re.search(pattern, filename)
            if match:
                return match.group(1).strip()
        
        return None
    
    def extract_client_list(self, filename: str) -> List[str]:
        """Extract list of client names from filename"""
        client_list_patterns = self.get_document_patterns('client_list_pattern')
        client_delimiters = self.get_document_patterns('client_delimiter')
        
        # First try to extract the client list section
        client_section = None
        for pattern_dict in client_list_patterns:
            pattern = pattern_dict['pattern']
            match = re.search(pattern, filename)
            if match:
                client_section = match.group(1).strip()
                break
        
        if not client_section:
            # Try a fallback approach - look for text between known markers
            # For example, between "Fee" and a date
            base_name = os.path.splitext(filename)[0]
            fee_match = re.search(r'Fee[s]?\s+(.+?)(?:\d{1,2}\.\d{1,2}\.\d{2,4}|\sQ[1-4]|\srecvd)', base_name, re.IGNORECASE)
            if fee_match:
                client_section = fee_match.group(1).strip()
            else:
                # Another fallback - look between provider and date
                provider = self.extract_provider_name(filename)
                if provider:
                    provider_match = re.search(re.escape(provider) + r'\s*[-:]\s*(?:401[kK].*?Fee[s]?\s*[-:]?\s*)?(.+?)(?:\d{1,2}\.\d{1,2}\.\d{2,4}|\sQ[1-4]|-\s*\d{1,2}\.\d{1,2}\.\d{2,4}|\srecvd)', filename, re.IGNORECASE)
                    if provider_match:
                        client_section = provider_match.group(1).strip()
        
        if not client_section:
            return []
        
        # Now split the client section using delimiters
        clients = [client_section]  # Start with the whole section
        
        for delimiter_dict in client_delimiters:
            delimiter = delimiter_dict['pattern']
            # Create a new list by splitting all current entries
            new_clients = []
            for client in clients:
                split_clients = re.split(delimiter, client)
                new_clients.extend([c.strip() for c in split_clients if c.strip()])
            clients = new_clients
        
        return clients
    
    def extract_document_date(self, filename: str) -> Optional[str]:
        """Extract date from filename and convert to YYYY-MM-DD format"""
        date_patterns = self.get_document_patterns('date_pattern')
        
        for pattern_dict in date_patterns:
            pattern = pattern_dict['pattern']
            match = re.search(pattern, filename)
            if match:
                # Handle different date formats
                if 'Q' in pattern:
                    # Handle quarter format (Q1-24)
                    quarter = int(match.group(1))
                    year_str = match.group(2)
                    
                    # Convert to full year if 2-digit
                    if len(year_str) == 2:
                        year = int(year_str)
                        if year < 50:
                            year = 2000 + year
                        else:
                            year = 1900 + year
                    else:
                        year = int(year_str)
                    
                    # Map quarter to middle month
                    month = (quarter * 3) - 1
                    return f"{year}-{month:02d}-15"
                else:
                    # Handle MM.DD.YY format
                    month = int(match.group(1))
                    day = int(match.group(2))
                    year_str = match.group(3) if len(match.groups()) >= 3 else "20"
                    
                    # Convert to full year if 2-digit
                    if len(year_str) == 2:
                        year = int(year_str)
                        if year < 50:
                            year = 2000 + year
                        else:
                            year = 1900 + year
                    else:
                        year = int(year_str)
                    
                    return f"{year}-{month:02d}-{day:02d}"
        
        # If no date found, use current date
        return datetime.now().strftime("%Y-%m-%d")
    
    def match_provider(self, provider_name: str) -> Optional[int]:
        """Match a provider name to a provider_id in the database"""
        if not provider_name:
            return None
            
        # Try exact match on provider_name
        provider = self.conn.execute(
            "SELECT provider_id FROM providers WHERE provider_name = ?",
            (provider_name,)
        ).fetchone()
        
        if provider:
            return provider['provider_id']
        
        # Try variant match
        providers = self.conn.execute(
            "SELECT provider_id, provider_name, name_variants FROM providers WHERE name_variants IS NOT NULL"
        ).fetchall()
        
        for p in providers:
            variants = p['name_variants'].split(',')
            for variant in variants:
                if variant.strip().lower() == provider_name.lower():
                    return p['provider_id']
        
        # Try fuzzy match (simple contains)
        providers = self.conn.execute(
            "SELECT provider_id, provider_name FROM providers"
        ).fetchall()
        
        for p in providers:
            if provider_name.lower() in p['provider_name'].lower() or p['provider_name'].lower() in provider_name.lower():
                return p['provider_id']
        
        return None
    
    def match_client(self, client_name: str) -> Optional[int]:
        """Match a client name to a client_id in the database"""
        if not client_name:
            return None
            
        # Try exact match on display_name
        client = self.conn.execute(
            "SELECT client_id FROM clients WHERE display_name = ? AND valid_to IS NULL",
            (client_name,)
        ).fetchone()
        
        if client:
            return client['client_id']
        
        # Try variant match
        clients = self.conn.execute(
            "SELECT client_id, display_name, name_variants FROM clients WHERE name_variants IS NOT NULL AND valid_to IS NULL"
        ).fetchall()
        
        for c in clients:
            if c['name_variants']:
                variants = c['name_variants'].split(',')
                for variant in variants:
                    if variant.strip().lower() == client_name.lower():
                        return c['client_id']
        
        # Try fuzzy match (simple contains)
        clients = self.conn.execute(
            "SELECT client_id, display_name FROM clients WHERE valid_to IS NULL"
        ).fetchall()
        
        for c in clients:
            if client_name.lower() in c['display_name'].lower() or c['display_name'].lower() in client_name.lower():
                return c['client_id']
        
        return None
    
    def find_matching_payments(self, client_id: int, provider_id: Optional[int], document_date: str) -> List[int]:
        """Find payments that likely match this document"""
        try:
            # Convert document_date to datetime for date calculations
            doc_date = datetime.strptime(document_date, "%Y-%m-%d")
            
            # Get days_to_match from system_config
            config = self.conn.execute(
                "SELECT config_value FROM system_config WHERE config_key = 'days_to_match_payment'"
            ).fetchone()
            
            days_to_match = 30  # Default
            if config and config['config_value'].isdigit():
                days_to_match = int(config['config_value'])
            
            # Calculate date range for matching
            date_min = (doc_date - timedelta(days=days_to_match)).strftime("%Y-%m-%d")
            date_max = (doc_date + timedelta(days=days_to_match)).strftime("%Y-%m-%d")
            
            # Build query based on available information
            query = """
                SELECT payment_id 
                FROM payments 
                WHERE client_id = ? 
                AND received_date BETWEEN ? AND ?
                AND valid_to IS NULL
            """
            params = [client_id, date_min, date_max]
            
            # Add provider filter if available
            if provider_id:
                query += """
                    AND contract_id IN (
                        SELECT contract_id FROM contracts 
                        WHERE provider_id = ? OR provider_name IN (
                            SELECT provider_name FROM providers WHERE provider_id = ?
                        )
                    )
                """
                params.extend([provider_id, provider_id])
            
            # Execute query
            payments = self.conn.execute(query, params).fetchall()
            return [p['payment_id'] for p in payments]
            
        except Exception as e:
            logging.error(f"Error finding matching payments: {str(e)}")
            return []
    
    def process_document(self, file_path: str) -> Optional[int]:
        """
        Process a single document from the mail dump folder
        
        Args:
            file_path: Full path to the document
            
        Returns:
            file_id if successful, None if skipped or error
        """
        try:
            filename = os.path.basename(file_path)
            
            # Check if this file is already processed
            existing = self.conn.execute(
                "SELECT file_id FROM client_files WHERE file_path = ?",
                (file_path,)
            ).fetchone()
            
            if existing:
                logging.info(f"File already processed: {filename}")
                return existing['file_id']
            
            # Check if this is a 401k document
            if not self.is_401k_document(filename):
                logging.info(f"Not a 401k document, skipping: {filename}")
                self.log_processing(filename, "skipped", "Not a 401k document")
                return None
            
            # Extract metadata
            provider_name = self.extract_provider_name(filename)
            client_names = self.extract_client_list(filename)
            document_date = self.extract_document_date(filename)
            
            # Match provider
            provider_id = self.match_provider(provider_name) if provider_name else None
            
            # Create database entry for the document
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT INTO client_files(file_path, original_filename, upload_date, document_date, provider_id, is_processed) 
                       VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, 0)""",
                    (file_path, filename, document_date, provider_id)
                )
                file_id = cursor.lastrowid
                
                # Store metadata
                metadata = {
                    "extracted_provider": provider_name,
                    "extracted_clients": client_names,
                    "processing_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                cursor.execute(
                    "UPDATE client_files SET metadata = ? WHERE file_id = ?",
                    (json.dumps(metadata), file_id)
                )
                
                # Process each client
                for client_name in client_names:
                    client_id = self.match_client(client_name)
                    if client_id:
                        # Find matching payments
                        payment_ids = self.find_matching_payments(client_id, provider_id, document_date)
                        
                        # Link to payments
                        for payment_id in payment_ids:
                            cursor.execute(
                                "INSERT INTO payment_files(payment_id, file_id) VALUES (?, ?)",
                                (payment_id, file_id)
                            )
                            
                        # Create shortcut
                        client_info = self.conn.execute(
                            "SELECT display_name FROM clients WHERE client_id = ?",
                            (client_id,)
                        ).fetchone()
                        
                        if client_info:
                            year = self.path_resolver.extract_year_from_filename(filename)
                            shortcut_path = self.path_resolver.get_shortcut_path(
                                client_info['display_name'], filename, year
                            )
                            self.path_resolver.create_windows_shortcut(file_path, shortcut_path)
            
            # Mark as processed
            with self.conn:
                self.conn.execute(
                    "UPDATE client_files SET is_processed = 1 WHERE file_id = ?",
                    (file_id,)
                )
            
            self.log_processing(filename, "processed", f"File ID: {file_id}", file_id)
            return file_id
            
        except Exception as e:
            logging.error(f"Error processing document {file_path}: {str(e)}")
            self.log_processing(os.path.basename(file_path), "error", str(e))
            return None
    
    def scan_mail_dump(self, year: Optional[int] = None) -> List[int]:
        """
        Scan the mail dump folder for unprocessed documents
        
        Args:
            year: Optional year to scan, defaults to current year
            
        Returns:
            List of processed file IDs
        """
        if year is None:
            year = datetime.now().year
            
        # Get mail dump path for this year
        mail_dump_path = self.path_resolver.get_mail_dump_path(year)
        
        if not os.path.exists(mail_dump_path):
            logging.warning(f"Mail dump path does not exist: {mail_dump_path}")
            return []
        
        # Get list of PDF files
        pdf_files = [f for f in os.listdir(mail_dump_path) if f.lower().endswith('.pdf')]
        
        processed_ids = []
        for pdf in pdf_files:
            file_path = os.path.join(mail_dump_path, pdf)
            file_id = self.process_document(file_path)
            if file_id:
                processed_ids.append(file_id)
        
        return processed_ids
    
    def log_processing(self, filename: str, status: str, details: Optional[str] = None, file_id: Optional[int] = None):
        """Log document processing status to the database"""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO processing_log(file_name, status, details, file_id) VALUES (?, ?, ?, ?)",
                    (filename, status, details, file_id)
                )
        except Exception as e:
            logging.error(f"Failed to log processing: {str(e)}")
    
    def get_unprocessed_documents(self) -> List[Dict]:
        """Get list of documents that have not been processed yet"""
        docs = self.conn.execute(
            """SELECT file_id, file_path, original_filename, document_date, provider_id
               FROM client_files 
               WHERE is_processed = 0
               ORDER BY upload_date DESC"""
        ).fetchall()
        
        return [dict(doc) for doc in docs]
