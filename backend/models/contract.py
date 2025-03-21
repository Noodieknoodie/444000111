# backend/models/contract.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FeeType(str, Enum):
    PERCENTAGE = "percentage"
    FLAT = "flat"

class PaymentSchedule(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

class ContractBase(BaseModel):
    client_id: int
    contract_number: Optional[str] = None
    provider_name: Optional[str] = None
    contract_start_date: Optional[str] = None
    fee_type: FeeType
    percent_rate: Optional[float] = None
    flat_rate: Optional[float] = None
    payment_schedule: PaymentSchedule
    num_people: Optional[int] = None
    is_active: bool = True
    
class ContractCreate(ContractBase):
    pass
    
class ContractUpdate(BaseModel):
    contract_number: Optional[str] = None
    provider_name: Optional[str] = None
    contract_start_date: Optional[str] = None
    fee_type: Optional[FeeType] = None
    percent_rate: Optional[float] = None
    flat_rate: Optional[float] = None
    payment_schedule: Optional[PaymentSchedule] = None
    num_people: Optional[int] = None
    is_active: Optional[bool] = None
    
class ContractResponse(ContractBase):
    contract_id: int
    valid_from: datetime
    valid_to: Optional[datetime] = None