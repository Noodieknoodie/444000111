# backend/main.py
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from fastapi_utils.tasks import repeat_every
from datetime import datetime
from api import clients_router, payments_router, contracts_router, files_router, contacts_router
from database import get_db_connection, backup_database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)

# Create FastAPI app
app = FastAPI(
    title="401(k) Payment Management System",
    description="Backend API for managing 401(k) plan payments",
    version="1.0.0"
)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients_router, prefix="/api/clients", tags=["clients"])
app.include_router(payments_router, prefix="/api/payments", tags=["payments"])
app.include_router(contracts_router, prefix="/api/contracts", tags=["contracts"])
app.include_router(files_router, prefix="/api/files", tags=["files"])
app.include_router(contacts_router, prefix="/api/contacts", tags=["contacts"])

@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    # Create backup of database
    backup_database()
    
    # Start period reference maintenance task
    asyncio.create_task(update_period_reference())

async def update_period_reference():
    """Update the period_reference table with current periods"""
    try:
        conn = get_db_connection()
        today = datetime.now()
        
        # For monthly: previous month
        if today.month == 1:
            current_month = 12
            current_month_year = today.year - 1
        else:
            current_month = today.month - 1
            current_month_year = today.year
            
        # For quarterly: previous quarter
        current_quarter = (today.month - 1) // 3
        if current_quarter == 0:
            current_quarter = 4
            current_quarter_year = today.year - 1
        else:
            current_quarter_year = today.year
            
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO period_reference(
                    reference_date, current_month_year, current_month,
                    current_quarter_year, current_quarter
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (today.strftime("%Y-%m-%d"), current_month_year, 
                 current_month, current_quarter_year, current_quarter)
            )
        
        logging.info("Period reference updated successfully")
            
    except Exception as e:
        logging.error(f"Failed to update period reference: {str(e)}")

@app.on_event("startup")
@repeat_every(seconds=60*60*24)  # Run once a day
async def scheduled_period_reference_update():
    """Daily scheduled task to update period reference"""
    await update_period_reference()

@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"message": "401(k) Payment Management System API"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": str(e)
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=6069, reload=True)