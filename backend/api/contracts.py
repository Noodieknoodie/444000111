# backend/api/contracts.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional
import sqlite3

from database import get_db_connection
from models.contract import (
    ContractBase, ContractCreate, ContractUpdate, ContractResponse
)

router = APIRouter()

@router.get("/active/{client_id}", response_model=ContractResponse)
async def get_active_contract(client_id: int = Path(..., description="The ID of the client")):
    """Fetches the active contract for a client"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT * FROM v_active_contracts 
            WHERE client_id = ?
            """, 
            (client_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="No active contract found for this client")
            
        return dict(result)
    finally:
        conn.close()

@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(contract_id: int = Path(..., description="The ID of the contract")):
    """Fetches a contract by ID"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM contracts WHERE contract_id = ? AND valid_to IS NULL", 
            (contract_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Contract not found")
            
        return dict(result)
    finally:
        conn.close()

@router.get("/client/{client_id}", response_model=List[ContractResponse])
async def get_client_contracts(
    client_id: int = Path(..., description="The ID of the client"),
    active_only: bool = Query(True, description="Only return active contracts")
):
    """Fetches all contracts for a client"""
    try:
        conn = get_db_connection()
        
        query = "SELECT * FROM contracts WHERE client_id = ? AND valid_to IS NULL"
        params = [client_id]
        
        if active_only:
            query += " AND is_active = 1"
            
        result = conn.execute(query, params).fetchall()
        return [dict(row) for row in result]
    finally:
        conn.close()

@router.post("/", response_model=ContractResponse, status_code=201)
async def create_contract(contract: ContractCreate):
    """Creates a new contract"""
    try:
        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO contracts(
                    client_id, contract_number, provider_name, contract_start_date,
                    fee_type, percent_rate, flat_rate, payment_schedule, num_people,
                    is_active, valid_from
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    contract.client_id, contract.contract_number, contract.provider_name,
                    contract.contract_start_date, contract.fee_type, contract.percent_rate,
                    contract.flat_rate, contract.payment_schedule, contract.num_people,
                    1 if contract.is_active else 0
                )
            )
            contract_id = cursor.lastrowid
            
        # Fetch the created contract
        result = conn.execute(
            "SELECT * FROM contracts WHERE contract_id = ?",
            (contract_id,)
        ).fetchone()
        
        return dict(result)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Contract could not be created (constraint violation)")
    finally:
        conn.close()

@router.put("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract: ContractUpdate,
    contract_id: int = Path(..., description="The ID of the contract to update")
):
    """Updates an existing contract"""
    try:
        conn = get_db_connection()
        
        # First check if contract exists
        existing = conn.execute(
            "SELECT * FROM contracts WHERE contract_id = ? AND valid_to IS NULL",
            (contract_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Build update fields dynamically based on provided values
        update_fields = []
        params = []
        
        if contract.contract_number is not None:
            update_fields.append("contract_number = ?")
            params.append(contract.contract_number)
            
        if contract.provider_name is not None:
            update_fields.append("provider_name = ?")
            params.append(contract.provider_name)
            
        if contract.contract_start_date is not None:
            update_fields.append("contract_start_date = ?")
            params.append(contract.contract_start_date)
            
        if contract.fee_type is not None:
            update_fields.append("fee_type = ?")
            params.append(contract.fee_type)
            
        if contract.percent_rate is not None:
            update_fields.append("percent_rate = ?")
            params.append(contract.percent_rate)
            
        if contract.flat_rate is not None:
            update_fields.append("flat_rate = ?")
            params.append(contract.flat_rate)
            
        if contract.payment_schedule is not None:
            update_fields.append("payment_schedule = ?")
            params.append(contract.payment_schedule)
            
        if contract.num_people is not None:
            update_fields.append("num_people = ?")
            params.append(contract.num_people)
            
        if contract.is_active is not None:
            update_fields.append("is_active = ?")
            params.append(1 if contract.is_active else 0)
            
        if not update_fields:
            # No fields to update
            return dict(existing)
            
        # Add contract_id to params
        params.append(contract_id)
        
        with conn:
            conn.execute(
                f"""
                UPDATE contracts 
                SET {', '.join(update_fields)}
                WHERE contract_id = ? AND valid_to IS NULL
                """,
                params
            )
            
        # Fetch the updated contract
        result = conn.execute(
            "SELECT * FROM contracts WHERE contract_id = ? AND valid_to IS NULL",
            (contract_id,)
        ).fetchone()
        
        return dict(result)
    finally:
        conn.close()

@router.delete("/{contract_id}", status_code=204)
async def delete_contract(contract_id: int = Path(..., description="The ID of the contract to delete")):
    """Soft-deletes a contract by setting valid_to"""
    try:
        conn = get_db_connection()
        
        # First check if contract exists
        existing = conn.execute(
            "SELECT * FROM contracts WHERE contract_id = ? AND valid_to IS NULL",
            (contract_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Contract not found")
            
        # Soft delete by setting valid_to
        with conn:
            conn.execute(
                "UPDATE contracts SET valid_to = CURRENT_TIMESTAMP WHERE contract_id = ? AND valid_to IS NULL",
                (contract_id,)
            )
            
        return None
    finally:
        conn.close()