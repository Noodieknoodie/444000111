# backend/models/file.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FileBase(BaseModel):
    client_id: int
    file_name: str
    onedrive_path: str
    
class FileCreate(FileBase):
    pass
    
class FileResponse(FileBase):
    file_id: int
    uploaded_at: datetime
    
class PaymentFileLink(BaseModel):
    payment_id: int
    file_id: int
    linked_at: Optional[datetime] = None