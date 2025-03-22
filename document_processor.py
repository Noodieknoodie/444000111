#!/usr/bin/env python3
# document_processor.py - Standalone script for document management
import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add the backend directory to the path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_dir)

from utils.document_processor import DocumentProcessor
from database import get_db_connection

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/document_processor.log"),
        logging.StreamHandler()
    ]
)

def ensure_log_directory():
    """Ensure log directory exists"""
    os.makedirs("logs", exist_ok=True)

def process_year(year):
    """Process all documents for a specific year"""
    processor = DocumentProcessor()
    logging.info(f"Processing documents for year {year}")
    
    processed_ids = processor.scan_mail_dump(year)
    logging.info(f"Processed {len(processed_ids)} documents")
    return processed_ids

def process_specific_file(file_path):
    """Process a specific file"""
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return None
    
    processor = DocumentProcessor()
    logging.info(f"Processing file: {file_path}")
    
    file_id = processor.process_document(file_path)
    if file_id:
        logging.info(f"Successfully processed file. ID: {file_id}")
    else:
        logging.warning(f"File processing failed or was skipped")
    
    return file_id

def list_unprocessed():
    """List all unprocessed documents"""
    processor = DocumentProcessor()
    docs = processor.get_unprocessed_documents()
    
    if not docs:
        print("No unprocessed documents found.")
        return
    
    print(f"Found {len(docs)} unprocessed documents:")
    for doc in docs:
        print(f"ID: {doc['file_id']} | {doc['original_filename']} | {doc['document_date']}")
    
    return docs

def main():
    """Main entry point"""
    ensure_log_directory()
    
    parser = argparse.ArgumentParser(description="Document processor for 401k payment system")
    parser.add_argument("--year", type=int, help="Process documents for a specific year")
    parser.add_argument("--file", type=str, help="Process a specific file")
    parser.add_argument("--list-unprocessed", action="store_true", help="List unprocessed documents")
    parser.add_argument("--force-all", action="store_true", help="Process all documents including already processed ones")
    
    args = parser.parse_args()
    
    if args.list_unprocessed:
        list_unprocessed()
        return
    
    if args.file:
        process_specific_file(args.file)
        return
    
    if args.year:
        process_year(args.year)
    else:
        # Process current year by default
        process_year(datetime.now().year)
    
if __name__ == "__main__":
    main()
