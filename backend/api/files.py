# backend/api/files.py
from fastapi import APIRouter, HTTPException, Path, UploadFile, File, Form, Response
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import logging

from database import get_db_connection
from utils.file_manager import FileManager
from models.file import FileResponse, FileCreate, PaymentFileLink

router = APIRouter()
file_manager = FileManager()

@router.post("/upload/{client_id}", response_model=FileResponse, status_code=201)
async def upload_file(
    client_id: int,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """Upload a file for a client and store the metadata"""
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
        
    try:
        result = file_manager.save_uploaded_file(client_id, file, file.filename)
        
        # Get the file metadata from the database
        conn = get_db_connection()
        try:
            file_info = conn.execute(
                "SELECT * FROM client_files WHERE file_id = ?",
                (result["file_id"],)
            ).fetchone()
            
            if not file_info:
                raise HTTPException(status_code=404, detail="File not found after upload")
                
            return dict(file_info)
        finally:
            conn.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="File upload failed")

@router.get("/client/{client_id}", response_model=List[FileResponse])
async def get_client_files(client_id: int):
    """Get all files for a client"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM client_files WHERE client_id = ? ORDER BY uploaded_at DESC",
            (client_id,)
        ).fetchall()
        
        return [dict(row) for row in result]
    finally:
        conn.close()

@router.get("/payment/{payment_id}", response_model=List[FileResponse])
async def get_payment_files(payment_id: int):
    """Get all files linked to a payment"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT cf.* 
            FROM client_files cf
            JOIN payment_files pf ON cf.file_id = pf.file_id
            WHERE pf.payment_id = ?
            ORDER BY cf.uploaded_at DESC
            """,
            (payment_id,)
        ).fetchall()
        
        return [dict(row) for row in result]
    finally:
        conn.close()

@router.get("/{file_id}")
async def get_file(file_id: int):
    """Retrieve a file by ID and serve it"""
    try:
        # Get file info from database
        file_info = file_manager.get_file_info(file_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")
            
        # Get the full path
        full_path = file_manager.get_full_path(file_info["onedrive_path"])
        
        if not full_path or not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found on disk")
            
        # Determine media type
        filename = file_info["file_name"]
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
            path=full_path,
            filename=filename,
            media_type=media_type
        )
    except Exception as e:
        logging.error(f"Error serving file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error serving file")

@router.post("/link", response_model=PaymentFileLink)
async def link_file_to_payment(link: PaymentFileLink):
    """Link an existing file to a payment"""
    try:
        conn = get_db_connection()
        
        # Check if file exists
        file_exists = conn.execute(
            "SELECT 1 FROM client_files WHERE file_id = ?",
            (link.file_id,)
        ).fetchone()
        
        if not file_exists:
            raise HTTPException(status_code=404, detail="File not found")
            
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
        raise HTTPException(status_code=400, detail=f"Failed to link file: {str(e)}")
    finally:
        conn.close()

@router.delete("/link/{payment_id}/{file_id}", status_code=204)
async def unlink_file_from_payment(payment_id: int, file_id: int):
    """Remove a file link from a payment"""
    try:
        conn = get_db_connection()
        
        # Check if link exists
        link_exists = conn.execute(
            "SELECT 1 FROM payment_files WHERE payment_id = ? AND file_id = ?",
            (payment_id, file_id)
        ).fetchone()
        
        if not link_exists:
            raise HTTPException(status_code=404, detail="File link not found")
            
        # Remove link
        with conn:
            conn.execute(
                "DELETE FROM payment_files WHERE payment_id = ? AND file_id = ?",
                (payment_id, file_id)
            )
            
        return None
    finally:
        conn.close()