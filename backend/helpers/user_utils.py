# user_utils.py
import os
import sqlite3
from pathlib import Path

_USERNAME = os.getlogin()

def get_user_base_path():
    # Updated path to match the actual location without the "401Ks/Current Plans/" part
    base_path = Path(f"C:/Users/{_USERNAME}/Hohimer Wealth Management/Hohimer Company Portal - Company/Hohimer Team Shared 4-15-19")
    return base_path

def validate_db_path(db_path):
    """Validate that the database file exists and is accessible."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found at: {db_path}")
    
    # Try to open the database to confirm it's a valid SQLite file
    try:
        conn = sqlite3.connect(str(db_path))
        conn.close()
        return True
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Error accessing database at {db_path}: {str(e)}")