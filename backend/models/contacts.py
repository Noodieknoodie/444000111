# backend/models/contact.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class ContactType(str, Enum):
    PRIMARY = "Primary"
    AUTHORIZED = "Authorized"
    PROVIDER = "Provider"
    OTHER = "Other"

class ContactBase(BaseModel):
    client_id: int
    contact_type: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    fax: Optional[str] = None
    physical_address: Optional[str] = None
    mailing_address: Optional[str] = None
    
class ContactCreate(ContactBase):
    pass
    
class ContactUpdate(BaseModel):
    contact_type: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    fax: Optional[str] = None
    physical_address: Optional[str] = None
    mailing_address: Optional[str] = None
    
class ContactResponse(ContactBase):
    contact_id: int
    valid_from: datetime
    valid_to: Optional[datetime] = None