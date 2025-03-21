# backend/api/clients.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional
import sqlite3

from backend.database import get_db_connection
from backend.models.client import (
    ClientBase, ClientCreate, ClientUpdate, ClientResponse,
    ClientSidebarModel, ClientDetailsModel
)

router = APIRouter()

@router.get("/sidebar", response_model=List[ClientSidebarModel])
async def get_client_sidebar():
    """Fetches client sidebar data directly from v_client_sidebar"""
    try:
        conn = get_db_connection()
        result = conn.execute("SELECT * FROM v_client_sidebar").fetchall()
        return [dict(row) for row in result]
    finally:
        conn.close()

@router.get("/details/{client_id}", response_model=ClientDetailsModel)
async def get_client_details(client_id: int = Path(..., description="The ID of the client")):
    """Fetches comprehensive client data from v_client_details"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM v_client_details WHERE client_id = ?", 
            (client_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Client not found")
            
        return dict(result)
    finally:
        conn.close()

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int = Path(..., description="The ID of the client")):
    """Fetches a client by ID"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM clients WHERE client_id = ? AND valid_to IS NULL", 
            (client_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Client not found")
            
        return dict(result)
    finally:
        conn.close()

@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    active_only: bool = Query(True, description="Only return active clients"),
    search: Optional[str] = Query(None, description="Search term for client names")
):
    """Fetches all clients, optionally filtered"""
    try:
        conn = get_db_connection()
        
        query = "SELECT * FROM clients WHERE valid_to IS NULL"
        params = []
        
        if search:
            query += " AND (display_name LIKE ? OR full_name LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
            
        query += " ORDER BY display_name"
        
        result = conn.execute(query, params).fetchall()
        return [dict(row) for row in result]
    finally:
        conn.close()

@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(client: ClientCreate):
    """Creates a new client"""
    try:
        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO clients(
                    display_name, full_name, ima_signed_date, 
                    onedrive_folder_path, valid_from
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    client.display_name, 
                    client.full_name, 
                    client.ima_signed_date,
                    client.onedrive_folder_path
                )
            )
            client_id = cursor.lastrowid
            
        # Fetch the created client
        result = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?",
            (client_id,)
        ).fetchone()
        
        return dict(result)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Client could not be created (constraint violation)")
    finally:
        conn.close()

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client: ClientUpdate,
    client_id: int = Path(..., description="The ID of the client to update")
):
    """Updates an existing client"""
    try:
        conn = get_db_connection()
        
        # First check if client exists
        existing = conn.execute(
            "SELECT * FROM clients WHERE client_id = ? AND valid_to IS NULL",
            (client_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Build update fields dynamically based on provided values
        update_fields = []
        params = []
        
        if client.display_name is not None:
            update_fields.append("display_name = ?")
            params.append(client.display_name)
            
        if client.full_name is not None:
            update_fields.append("full_name = ?")
            params.append(client.full_name)
            
        if client.ima_signed_date is not None:
            update_fields.append("ima_signed_date = ?")
            params.append(client.ima_signed_date)
            
        if client.onedrive_folder_path is not None:
            update_fields.append("onedrive_folder_path = ?")
            params.append(client.onedrive_folder_path)
            
        if not update_fields:
            # No fields to update
            return dict(existing)
            
        # Add client_id to params
        params.append(client_id)
        
        with conn:
            conn.execute(
                f"""
                UPDATE clients 
                SET {', '.join(update_fields)}
                WHERE client_id = ? AND valid_to IS NULL
                """,
                params
            )
            
        # Fetch the updated client
        result = conn.execute(
            "SELECT * FROM clients WHERE client_id = ? AND valid_to IS NULL",
            (client_id,)
        ).fetchone()
        
        return dict(result)
    finally:
        conn.close()

@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int = Path(..., description="The ID of the client to delete")):
    """Soft-deletes a client by setting valid_to"""
    try:
        conn = get_db_connection()
        
        # First check if client exists
        existing = conn.execute(
            "SELECT * FROM clients WHERE client_id = ? AND valid_to IS NULL",
            (client_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Client not found")
            
        # Soft delete by setting valid_to
        with conn:
            conn.execute(
                "UPDATE clients SET valid_to = CURRENT_TIMESTAMP WHERE client_id = ? AND valid_to IS NULL",
                (client_id,)
            )
            
        return None
    finally:
        conn.close()