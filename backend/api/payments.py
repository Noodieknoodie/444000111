# backend/api/payments.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile, File, Form
from typing import List, Optional
import sqlite3
import json

from backend.database import get_db_connection
from backend.utils.file_manager import FileManager
from backend.models.payment import (
    PaymentCreate, PaymentUpdate, PaymentResponse, PaymentHistoryModel,
    MissingPaymentModel
)

router = APIRouter()
file_manager = FileManager()

@router.get("/history/{client_id}", response_model=List[PaymentHistoryModel])
async def get_payment_history(client_id: int = Path(..., description="The ID of the client")):
    """Fetches payment history from v_payment_history"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM v_payment_history WHERE client_id = ? ORDER BY payment_date_formatted DESC", 
            (client_id,)
        ).fetchall()
        return [dict(row) for row in result]
    finally:
        conn.close()

@router.get("/last/{client_id}", response_model=PaymentHistoryModel)
async def get_last_payment(client_id: int = Path(..., description="The ID of the client")):
    """Fetches the last payment for a client from v_last_payment"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM v_last_payment WHERE client_id = ?", 
            (client_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="No payments found for this client")
            
        return dict(result)
    finally:
        conn.close()

@router.get("/missing/{client_id}", response_model=MissingPaymentModel)
async def get_missing_payments(client_id: int = Path(..., description="The ID of the client")):
    """Fetches missing payments for a client"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM v_missing_payment_periods WHERE client_id = ?", 
            (client_id,)
        ).fetchone()
        
        if not result:
            # Return empty missing periods if none found
            client = conn.execute(
                "SELECT client_id, display_name FROM clients WHERE client_id = ? AND valid_to IS NULL",
                (client_id,)
            ).fetchone()
            
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
                
            return {
                "client_id": client_id,
                "display_name": client["display_name"],
                "missing_periods": ""
            }
            
        return dict(result)
    finally:
        conn.close()

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: int = Path(..., description="The ID of the payment")):
    """Fetches a payment by ID"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ? AND valid_to IS NULL", 
            (payment_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Payment not found")
            
        return dict(result)
    finally:
        conn.close()

@router.post("/", response_model=dict, status_code=201)
async def create_payment(
    payment_data: str = Form(...),
    file: Optional[UploadFile] = File(None)
):
    """Creates a new payment with optional file attachment"""
    # Parse the payment data from form
    try:
        payment = PaymentCreate.parse_raw(payment_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payment data: {str(e)}")
    
    file_id = None
    try:
        conn = get_db_connection()
        
        # Handle file upload if provided
        if file and file.filename:
            file_result = file_manager.save_uploaded_file(
                payment.client_id,
                file,
                file.filename
            )
            file_id = file_result["file_id"]
        
        # Insert payment
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO payments(
                    contract_id, client_id, received_date, total_assets, 
                    actual_fee, method, notes, applied_start_month, 
                    applied_start_month_year, applied_end_month, applied_end_month_year,
                    applied_start_quarter, applied_start_quarter_year, 
                    applied_end_quarter, applied_end_quarter_year, valid_from
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    payment.contract_id, payment.client_id, payment.received_date, 
                    payment.total_assets, payment.actual_fee, payment.method, 
                    payment.notes, payment.applied_start_month, payment.applied_start_month_year,
                    payment.applied_end_month, payment.applied_end_month_year,
                    payment.applied_start_quarter, payment.applied_start_quarter_year,
                    payment.applied_end_quarter, payment.applied_end_quarter_year
                )
            )
            payment_id = cursor.lastrowid
            
            # Link file if uploaded
            if file_id:
                cursor.execute(
                    "INSERT INTO payment_files(payment_id, file_id, linked_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (payment_id, file_id)
                )
            
        return {"payment_id": payment_id, "success": True, "file_id": file_id}
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Payment could not be created: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating payment: {str(e)}")
    finally:
        conn.close()

@router.put("/{payment_id}", response_model=dict)
async def update_payment(
    payment_id: int = Path(...),
    payment_data: str = Form(...),
    file: Optional[UploadFile] = File(None)
):
    """Updates an existing payment with optional new file attachment"""
    # Parse the payment data from form
    try:
        payment = PaymentUpdate.parse_raw(payment_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payment data: {str(e)}")
    
    file_id = None
    try:
        conn = get_db_connection()
        
        # Check if payment exists
        existing = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ? AND valid_to IS NULL",
            (payment_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Payment not found")
            
        client_id = existing["client_id"]
            
        # Handle file upload if provided
        if file and file.filename:
            file_result = file_manager.save_uploaded_file(
                client_id,
                file,
                file.filename
            )
            file_id = file_result["file_id"]
        
        # Build update fields dynamically
        update_fields = []
        params = []
        
        if payment.received_date is not None:
            update_fields.append("received_date = ?")
            params.append(payment.received_date)
            
        if payment.total_assets is not None:
            update_fields.append("total_assets = ?")
            params.append(payment.total_assets)
            
        if payment.actual_fee is not None:
            update_fields.append("actual_fee = ?")
            params.append(payment.actual_fee)
            
        if payment.method is not None:
            update_fields.append("method = ?")
            params.append(payment.method)
            
        if payment.notes is not None:
            update_fields.append("notes = ?")
            params.append(payment.notes)
            
        # Period fields
        if payment.applied_start_month is not None:
            update_fields.append("applied_start_month = ?")
            params.append(payment.applied_start_month)
            
        if payment.applied_start_month_year is not None:
            update_fields.append("applied_start_month_year = ?")
            params.append(payment.applied_start_month_year)
            
        if payment.applied_end_month is not None:
            update_fields.append("applied_end_month = ?")
            params.append(payment.applied_end_month)
            
        if payment.applied_end_month_year is not None:
            update_fields.append("applied_end_month_year = ?")
            params.append(payment.applied_end_month_year)
            
        if payment.applied_start_quarter is not None:
            update_fields.append("applied_start_quarter = ?")
            params.append(payment.applied_start_quarter)
            
        if payment.applied_start_quarter_year is not None:
            update_fields.append("applied_start_quarter_year = ?")
            params.append(payment.applied_start_quarter_year)
            
        if payment.applied_end_quarter is not None:
            update_fields.append("applied_end_quarter = ?")
            params.append(payment.applied_end_quarter)
            
        if payment.applied_end_quarter_year is not None:
            update_fields.append("applied_end_quarter_year = ?")
            params.append(payment.applied_end_quarter_year)
            
        if update_fields:
            # Add payment_id to params
            params.append(payment_id)
            
            with conn:
                conn.execute(
                    f"""
                    UPDATE payments 
                    SET {', '.join(update_fields)}
                    WHERE payment_id = ? AND valid_to IS NULL
                    """,
                    params
                )
                
        # Link file if uploaded
        if file_id:
            with conn:
                conn.execute(
                    "INSERT INTO payment_files(payment_id, file_id, linked_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (payment_id, file_id)
                )
            
        return {"payment_id": payment_id, "success": True, "updated": bool(update_fields), "file_id": file_id}
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Payment could not be updated: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating payment: {str(e)}")
    finally:
        conn.close()

@router.delete("/{payment_id}", status_code=204)
async def delete_payment(payment_id: int = Path(..., description="The ID of the payment to delete")):
    """Soft-deletes a payment by setting valid_to"""
    try:
        conn = get_db_connection()
        
        # Check if payment exists
        existing = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ? AND valid_to IS NULL",
            (payment_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Payment not found")
            
        # Soft delete
        with conn:
            conn.execute(
                "UPDATE payments SET valid_to = CURRENT_TIMESTAMP WHERE payment_id = ? AND valid_to IS NULL",
                (payment_id,)
            )
            
        return None
    finally:
        conn.close()