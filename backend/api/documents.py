# backend/api/documents.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
import os
import logging
from datetime import datetime

from database import get_db_connection
from models.file import FileResponse, FileCreate, PaymentFileLink
from utils.file_manager import FileManager
from utils.document_processor import DocumentProcessor

router = APIRouter()
file_manager = FileManager()
doc_processor = DocumentProcessor()

@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    client_ids: List[int] = Form(...),
    payment_ids: Optional[List[int]] = Form(None),
    provider_id: Optional[int] = Form(None)
):
    """
    Upload a document and associate it with clients and payments
    Implements the "Store Once, Link Everywhere" pattern
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
        
    try:
        # Save document to mail dump (Store Once)
        result = file_manager.save_document_to_mail_dump(file, file.filename, provider_id=provider_id)
        file_id = result["file_id"]
        
        # Process client associations and create shortcuts (Link Everywhere)
        conn = get_db_connection()
        try:
            # For each client, create a shortcut
            for client_id in client_ids:
                # Get client info
                client = conn.execute(
                    "SELECT display_name FROM clients WHERE client_id = ?",
                    (client_id,)
                ).fetchone()
                
                if not client:
                    continue
                
                # Extract year from filename for shortcut organization
                year = file_manager.path_resolver.extract_year_from_filename(file.filename)
                
                # Create shortcut in client folder
                shortcut_path = file_manager.path_resolver.get_shortcut_path(
                    client['display_name'], file.filename, year
                )
                file_manager.path_resolver.create_windows_shortcut(result["file_path"], shortcut_path)
            
            # Link to payments if provided
            if payment_ids:
                for payment_id in payment_ids:
                    conn.execute(
                        "INSERT INTO payment_files(payment_id, file_id) VALUES (?, ?)",
                        (payment_id, file_id)
                    )
            
            # Mark as processed
            conn.execute(
                "UPDATE client_files SET is_processed = 1 WHERE file_id = ?",
                (file_id,)
            )
            conn.commit()
            
            # Get the file metadata from the database
            file_info = conn.execute(
                "SELECT * FROM client_files WHERE file_id = ?",
                (file_id,)
            ).fetchone()
            
            if not file_info:
                raise HTTPException(status_code=404, detail="File not found after upload")
                
            # Schedule background task to process other similar documents
            background_tasks.add_task(
                scan_mail_dump_for_similar_documents,
                file.filename,
                datetime.now().year
            )
                
            return dict(file_info)
        finally:
            conn.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="File upload failed")

@router.get("/payment/{payment_id}", response_model=List[Dict[str, Any]])
async def get_documents_for_payment(payment_id: int):
    """Get all documents linked to a payment using the DocumentView"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT *
            FROM DocumentView
            WHERE payment_id = ?
            """,
            (payment_id,)
        ).fetchall()
        
        return [dict(row) for row in result]
    except Exception as e:
        logging.error(f"Error retrieving documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents")

@router.get("/{file_id}")
async def get_document(file_id: int):
    """Retrieve a document by ID and serve it"""
    try:
        # Get file info from database
        conn = get_db_connection()
        file_info = conn.execute(
            "SELECT file_path, original_filename FROM client_files WHERE file_id = ?", 
            (file_id,)
        ).fetchone()
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Document not found")
            
        file_path = file_info["file_path"]
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document file not found on disk")
            
        # Determine media type
        filename = file_info["original_filename"]
        media_type = None
        
        if filename.lower().endswith(".pdf"):
            media_type = "application/pdf"
        elif filename.lower().endswith((".jpg", ".jpeg")):
            media_type = "image/jpeg"
        elif filename.lower().endswith(".png"):
            media_type = "image/png"
        else:
            media_type = "application/octet-stream"
            
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
    except Exception as e:
        logging.error(f"Error serving document: {str(e)}")
        raise HTTPException(status_code=500, detail="Error serving document")

@router.post("/link", response_model=PaymentFileLink)
async def link_document_to_payment(link: PaymentFileLink):
    """Link an existing document to a payment"""
    try:
        conn = get_db_connection()
        
        # Check if file exists
        file_exists = conn.execute(
            "SELECT 1 FROM client_files WHERE file_id = ?",
            (link.file_id,)
        ).fetchone()
        
        if not file_exists:
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Check if payment exists
        payment_exists = conn.execute(
            "SELECT 1 FROM payments WHERE payment_id = ? AND valid_to IS NULL",
            (link.payment_id,)
        ).fetchone()
        
        if not payment_exists:
            raise HTTPException(status_code=404, detail="Payment not found")
            
        # Create link
        with conn:
            conn.execute(
                "INSERT INTO payment_files(payment_id, file_id, linked_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (link.payment_id, link.file_id)
            )
            
        return link
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to link document: {str(e)}")

@router.post("/process", response_model=Dict[str, Any])
async def process_documents(year: Optional[int] = None):
    """
    Manually trigger document processing for the mail dump folder
    """
    try:
        if year is None:
            year = datetime.now().year
            
        processor = DocumentProcessor()
        processed_ids = processor.scan_mail_dump(year)
        
        return {
            "success": True,
            "processed_count": len(processed_ids),
            "processed_ids": processed_ids
        }
    except Exception as e:
        logging.error(f"Document processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")

@router.get("/unprocessed", response_model=List[Dict[str, Any]])
async def get_unprocessed_documents():
    """Get list of documents that haven't been processed yet"""
    try:
        processor = DocumentProcessor()
        return processor.get_unprocessed_documents()
    except Exception as e:
        logging.error(f"Error retrieving unprocessed documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unprocessed documents")

async def scan_mail_dump_for_similar_documents(filename: str, year: int):
    """
    Background task to scan for documents similar to the one just uploaded
    """
    try:
        logging.info(f"Scanning mail dump for documents similar to {filename}")
        processor = DocumentProcessor()
        processor.scan_mail_dump(year)
    except Exception as e:
        logging.error(f"Background scan failed: {str(e)}")
