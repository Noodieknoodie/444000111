# backend/models/client.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class ClientBase(BaseModel):
    display_name: str
    full_name: Optional[str] = None
    ima_signed_date: Optional[str] = None
    onedrive_folder_path: Optional[str] = None
    
class ClientCreate(ClientBase):
    pass
    
class ClientUpdate(ClientBase):
    display_name: Optional[str] = None
    
class ClientResponse(ClientBase):
    client_id: int
    valid_from: datetime
    valid_to: Optional[datetime] = None
    
class ClientSidebarModel(BaseModel):
    client_id: int
    display_name: str
    initials: str
    provider_name: str
    payment_status: str
    formatted_current_period: str
    
class ClientDetailsModel(BaseModel):
    client_id: int
    display_name: str
    full_name: Optional[str] = None
    ima_signed_date: Optional[str] = None
    address: Optional[str] = None
    contract_id: int
    contract_number: Optional[str] = None
    provider_name: Optional[str] = None
    payment_schedule: str
    fee_type: str
    percent_rate: Optional[float] = None
    flat_rate: Optional[float] = None
    participants: Optional[int] = None
    payment_status: str
    current_period: str
    missing_payment_count: int
    client_days: int
    client_since_formatted: str
