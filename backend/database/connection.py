# backend/database/connection.py
import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
import shutil

from config import settings

def get_db_connection(test_mode=False):
    """
    Establishes a connection to the SQLite database with fallback paths.
    
    Args:
        test_mode (bool): If True, connects to the test database
        
    Returns:
        sqlite3.Connection: Database connection with Row factory enabled
    """
    if test_mode:
        path = settings.get_test_db_path()
        if os.path.exists(path):
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            raise FileNotFoundError(f"Test database not found at {path}")
    
    # Try each path in order
    paths = settings.get_db_paths()
    errors = []
    
    for path in paths:
        try:
            if os.path.exists(path):
                conn = sqlite3.connect(path)
                conn.row_factory = sqlite3.Row
                logging.info(f"Connected to database at {path}")
                return conn
        except Exception as e:
            errors.append(f"Failed to connect to {path}: {str(e)}")
    
    # If we reach here, all connections failed
    error_msg = "\n".join(errors)
    logging.error(f"Failed to connect to any database:\n{error_msg}")
    raise ConnectionError("Could not connect to any database. See logs for details.")

def backup_database():
    """Creates a timestamped backup of the current database"""
    try:
        # Get current database path
        conn = get_db_connection()
        current_path = conn.execute("PRAGMA database_list").fetchone()[2]
        conn.close()
        
        # Create backup filename with timestamp
        backup_dir = settings.get_backup_path()
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy the database file
        shutil.copy2(current_path, backup_path)
        logging.info(f"Database backup created at {backup_path}")
        
        # Implement retention policy (keep last 7 backups)
        cleanup_old_backups(backup_dir)
        
        return True
    except Exception as e:
        logging.error(f"Backup failed: {str(e)}")
        return False

def cleanup_old_backups(backup_dir):
    """Retains only the 7 most recent backups"""
    try:
        backups = [f for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".db")]
        backups.sort(reverse=True)  # Newest first
        
        # Remove older backups beyond the first 7
        for old_backup in backups[7:]:
            os.remove(os.path.join(backup_dir, old_backup))
            logging.info(f"Removed old backup: {old_backup}")
    except Exception as e:
        logging.error(f"Failed to clean up old backups: {str(e)}")