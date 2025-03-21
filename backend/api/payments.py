# backend/api/payments.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile, File, Form
from typing import List, Optional
import sqlite3
import json

from database import get_db_connection
from utils.file_manager import FileManager
from models.payment import (
    PaymentCreate, PaymentUpdate, PaymentResponse, PaymentHistoryModel,
    MissingPaymentModel
)

router = APIRouter()
file_manager = FileManager()

# Updated payment history endpoint with comprehensive error handling
@router.get("/history/{client_id}", response_model=List[PaymentHistoryModel])
async def get_payment_history(client_id: int = Path(..., description="The ID of the client")):
    """Fetches payment history from v_payment_history with robust error handling"""
    try:
        conn = get_db_connection()
        
        # Get raw data from view
        try:
            result = conn.execute(
                "SELECT * FROM v_payment_history WHERE client_id = ? ORDER BY payment_date_formatted DESC", 
                (client_id,)
            ).fetchall()
        except Exception as e:
            # Log the database query error
            print(f"Database query error: {str(e)}")
            # Return empty list rather than failing
            return []
        
        # Process each row individually and catch errors
        processed_results = []
        
        for row in result:
            try:
                # Convert the row to a dict
                row_dict = dict(row)
                
                # Convert boolean fields - handle any format
                for field in ['is_split', 'is_estimated_aum', 'is_estimated_fee']:
                    try:
                        row_dict[field] = bool(row_dict.get(field, 0))
                    except Exception:
                        row_dict[field] = False
                
                # Ensure all required string fields exist and aren't None
                for field in ['display_name', 'payment_date_formatted', 'period_start_formatted']:
                    if field not in row_dict or row_dict[field] is None:
                        row_dict[field] = "" if field != 'display_name' else "Unknown"
                
                # Ensure period_end_formatted exists (it can be empty)
                if 'period_end_formatted' not in row_dict or row_dict['period_end_formatted'] is None:
                    row_dict['period_end_formatted'] = ""
                
                # Ensure all optional fields have proper null values when missing
                for field in ['notes', 'method', 'onedrive_path', 'file_name', 
                             'variance_classification', 'estimated_variance_classification']:
                    if field not in row_dict:
                        row_dict[field] = None
                
                # Handle numeric fields with careful conversion
                # Integer fields
                for field in ['payment_id', 'client_id', 'aum', 'displayed_aum', 'file_id']:
                    try:
                        if field in row_dict and row_dict[field] is not None:
                            row_dict[field] = int(row_dict[field])
                        elif field in ['payment_id', 'client_id']:  # These are required
                            if field not in row_dict or row_dict[field] is None:
                                # Skip this record if missing required fields
                                raise ValueError(f"Missing required field: {field}")
                    except Exception:
                        if field in ['payment_id', 'client_id']:
                            # Skip this record
                            raise ValueError(f"Invalid required field: {field}")
                        else:
                            row_dict[field] = None
                
                # Float fields (careful with actual_fee which is required)
                for field in ['expected_fee', 'displayed_expected_fee', 'variance_amount', 
                             'estimated_variance_amount', 'actual_fee']:
                    try:
                        if field in row_dict and row_dict[field] is not None:
                            row_dict[field] = float(row_dict[field])
                        elif field == 'actual_fee':  # This is required
                            row_dict[field] = 0.0  # Use zero as fallback for actual_fee
                    except Exception:
                        if field == 'actual_fee':
                            row_dict[field] = 0.0
                        else:
                            row_dict[field] = None
                
                # Add successfully processed row
                processed_results.append(row_dict)
                
            except Exception as e:
                # Log the error but continue processing other rows
                print(f"Error processing row: {str(e)}")
                # Skip this row and continue with the next one
                continue
                
        return processed_results
    except Exception as e:
        # Log the error
        print(f"Unhandled error in payment history: {str(e)}")
        # Return empty list instead of error
        return []
    finally:
        try:
            conn.close()
        except:
            pass
        
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
        
        # Convert to dict and fix boolean fields
        result_dict = dict(result)
        result_dict['is_split'] = bool(result_dict.get('is_split', 0))
        result_dict['is_estimated_aum'] = bool(result_dict.get('is_estimated_aum', 0))
        result_dict['is_estimated_fee'] = bool(result_dict.get('is_estimated_fee', 0))
            
        return result_dict
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