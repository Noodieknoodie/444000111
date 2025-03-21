# backend/api/__init__.py
from .clients import router as clients_router
from .payments import router as payments_router
from .contracts import router as contracts_router
from .files import router as files_router
from .contacts import router as contacts_router