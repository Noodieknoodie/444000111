# backend/models/payment.py
from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import datetime
from enum import Enum

class PaymentStatus(str, Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"

class VarianceClassification(str, Enum):
    OVERPAID = "Overpaid"
    UNDERPAID = "Underpaid"
    WITHIN_TARGET = "Within Target"

class PaymentBase(BaseModel):
    contract_id: int
    client_id: int
    received_date: str
    total_assets: Optional[int] = None
    actual_fee: float
    method: Optional[str] = None
    notes: Optional[str] = None
    
class PaymentCreate(PaymentBase):
    applied_start_month: Optional[int] = None
    applied_start_month_year: Optional[int] = None
    applied_end_month: Optional[int] = None
    applied_end_month_year: Optional[int] = None
    applied_start_quarter: Optional[int] = None
    applied_start_quarter_year: Optional[int] = None
    applied_end_quarter: Optional[int] = None
    applied_end_quarter_year: Optional[int] = None
    file_id: Optional[int] = None
    
class PaymentUpdate(BaseModel):
    received_date: Optional[str] = None
    total_assets: Optional[int] = None
    actual_fee: Optional[float] = None
    method: Optional[str] = None
    notes: Optional[str] = None
    applied_start_month: Optional[int] = None
    applied_start_month_year: Optional[int] = None
    applied_end_month: Optional[int] = None
    applied_end_month_year: Optional[int] = None
    applied_start_quarter: Optional[int] = None
    applied_start_quarter_year: Optional[int] = None
    applied_end_quarter: Optional[int] = None
    applied_end_quarter_year: Optional[int] = None
    
class PaymentResponse(PaymentBase):
    payment_id: int
    valid_from: datetime
    valid_to: Optional[datetime] = None
    applied_start_month: Optional[int] = None
    applied_start_month_year: Optional[int] = None
    applied_end_month: Optional[int] = None
    applied_end_month_year: Optional[int] = None
    applied_start_quarter: Optional[int] = None
    applied_start_quarter_year: Optional[int] = None
    applied_end_quarter: Optional[int] = None
    applied_end_quarter_year: Optional[int] = None
    
class PaymentHistoryModel(BaseModel):
    payment_id: int
    client_id: int
    display_name: str
    payment_date_formatted: str
    period_start_formatted: str
    period_end_formatted: Optional[str] = None
    aum: Optional[int] = None
    displayed_aum: Optional[int] = None
    is_estimated_aum: bool = False
    expected_fee: Optional[float] = None
    displayed_expected_fee: Optional[float] = None
    is_estimated_fee: bool = False
    actual_fee: float
    variance_amount: Optional[float] = None
    variance_classification: Optional[VarianceClassification] = None
    is_split: bool
    estimated_variance_amount: Optional[float] = None
    estimated_variance_classification: Optional[VarianceClassification] = None
    file_id: Optional[int] = None
    file_name: Optional[str] = None
    onedrive_path: Optional[str] = None
    method: Optional[str] = None
    notes: Optional[str] = None
    
class MissingPaymentModel(BaseModel):
    client_id: int
    display_name: str
    missing_periods: str
