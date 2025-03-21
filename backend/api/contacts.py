# backend/api/contacts.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional
import sqlite3

from database import get_db_connection
from models.contacts import (
    ContactBase, ContactCreate, ContactUpdate, ContactResponse, ContactType
)

router = APIRouter()

@router.get("/client/{client_id}", response_model=List[ContactResponse])
async def get_client_contacts(
    client_id: int = Path(..., description="The ID of the client"),
    contact_type: Optional[str] = Query(None, description="Filter by contact type")
):
    """Fetches all contacts for a client, optionally filtered by type"""
    try:
        conn = get_db_connection()
        
        query = "SELECT * FROM contacts WHERE client_id = ? AND valid_to IS NULL"
        params = [client_id]
        
        if contact_type:
            query += " AND contact_type = ?"
            params.append(contact_type)
            
        query += " ORDER BY contact_type, contact_name"
        
        result = conn.execute(query, params).fetchall()
        return [dict(row) for row in result]
    finally:
        conn.close()

@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: int = Path(..., description="The ID of the contact")):
    """Fetches a contact by ID"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM contacts WHERE contact_id = ? AND valid_to IS NULL", 
            (contact_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Contact not found")
            
        return dict(result)
    finally:
        conn.close()

@router.post("/", response_model=ContactResponse, status_code=201)
async def create_contact(contact: ContactCreate):
    """Creates a new contact"""
    try:
        conn = get_db_connection()
        
        # Validate client exists
        client = conn.execute(
            "SELECT 1 FROM clients WHERE client_id = ? AND valid_to IS NULL",
            (contact.client_id,)
        ).fetchone()
        
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO contacts(
                    client_id, contact_type, contact_name, phone, email, 
                    fax, physical_address, mailing_address, valid_from
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    contact.client_id, contact.contact_type, contact.contact_name,
                    contact.phone, contact.email, contact.fax,
                    contact.physical_address, contact.mailing_address
                )
            )
            contact_id = cursor.lastrowid
            
        # Fetch the created contact
        result = conn.execute(
            "SELECT * FROM contacts WHERE contact_id = ?",
            (contact_id,)
        ).fetchone()
        
        return dict(result)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Contact could not be created (constraint violation)")
    finally:
        conn.close()

@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact: ContactUpdate,
    contact_id: int = Path(..., description="The ID of the contact to update")
):
    """Updates an existing contact"""
    try:
        conn = get_db_connection()
        
        # First check if contact exists
        existing = conn.execute(
            "SELECT * FROM contacts WHERE contact_id = ? AND valid_to IS NULL",
            (contact_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        # Build update fields dynamically based on provided values
        update_fields = []
        params = []
        
        if contact.contact_type is not None:
            update_fields.append("contact_type = ?")
            params.append(contact.contact_type)
            
        if contact.contact_name is not None:
            update_fields.append("contact_name = ?")
            params.append(contact.contact_name)
            
        if contact.phone is not None:
            update_fields.append("phone = ?")
            params.append(contact.phone)
            
        if contact.email is not None:
            update_fields.append("email = ?")
            params.append(contact.email)
            
        if contact.fax is not None:
            update_fields.append("fax = ?")
            params.append(contact.fax)
            
        if contact.physical_address is not None:
            update_fields.append("physical_address = ?")
            params.append(contact.physical_address)
            
        if contact.mailing_address is not None:
            update_fields.append("mailing_address = ?")
            params.append(contact.mailing_address)
            
        if not update_fields:
            # No fields to update
            return dict(existing)
            
        # Add contact_id to params
        params.append(contact_id)
        
        with conn:
            conn.execute(
                f"""
                UPDATE contacts 
                SET {', '.join(update_fields)}
                WHERE contact_id = ? AND valid_to IS NULL
                """,
                params
            )
            
        # Fetch the updated contact
        result = conn.execute(
            "SELECT * FROM contacts WHERE contact_id = ? AND valid_to IS NULL",
            (contact_id,)
        ).fetchone()
        
        return dict(result)
    finally:
        conn.close()

@router.delete("/{contact_id}", status_code=204)
async def delete_contact(contact_id: int = Path(..., description="The ID of the contact to delete")):
    """Soft-deletes a contact by setting valid_to"""
    try:
        conn = get_db_connection()
        
        # First check if contact exists
        existing = conn.execute(
            "SELECT * FROM contacts WHERE contact_id = ? AND valid_to IS NULL",
            (contact_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Contact not found")
            
        # Soft delete by setting valid_to
        with conn:
            conn.execute(
                "UPDATE contacts SET valid_to = CURRENT_TIMESTAMP WHERE contact_id = ? AND valid_to IS NULL",
                (contact_id,)
            )
            
        return None
    finally:
        conn.close()