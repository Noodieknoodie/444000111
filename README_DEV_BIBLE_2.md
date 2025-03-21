# README_DEV_BIBLE_2.md

# 401(k) Payment Management System: Technical Implementation Guide

## System Overview

The 401(k) Payment Management System is a Windows desktop application designed to replace an Excel-based workflow for a small company (~5 people) that manages 401(k) plans for client businesses. The application runs offline with local file storage via OneDrive and uses SQLite for data management.

### Core Business Context

- Payments are collected **in arrears** (after the period ends)
- Monthly clients pay for the previous month
- Quarterly clients pay for the previous quarter
- The system tracks client payments, detects missed payments, calculates fees and variances, stores documents, and generates reports

## Technical Architecture

### Backend Components

- **Language**: Python 
- **Framework**: FastAPI
- **Data Validation**: Pydantic
- **Database**: SQLite with direct SQL queries (no ORM)
- **File Storage**: Local OneDrive integration

### Frontend Components

- **Framework**: React with Next.js
- **Styling**: Tailwind CSS
- **UI Components**: Shadcn UI, Radix UI
- **State Management**: React's built-in state management (Context API)

### Database Architecture

The database leverages SQLite views for complex business logic, with a tiered structure:
1. **Foundation Views**: Handle period calculations and payment expansion
2. **Business Logic Views**: Calculate expected fees, variances, missing payments
3. **UI Views**: Ready-to-use data for specific UI components

## Application Structure

```
// YOU DECIDE WHAT IS BEST FOR THIS PROJECT AND WHAT WOULD RESONATE WITH ME. IM TRUSTING YOU TO MAKE THE BEST DECISIONS.
```

## Configuration Management

The application uses a YAML configuration file to manage database and file paths:

```yaml
database:
  office: C:/Users/{username}/Hohimer Wealth Management/Hohimer Company Portal - Company/Hohimer Team Shared 4-15-19/HohimerPro/database/401k_payments_66.db
  home: backend/data/401k_payments_66.db
  test: backend/data/401k_payments_test.db
  fallback: backend/data/401k_payments_master.db

files:
  mail_dump: C:/Users/{username}/Hohimer Wealth Management/Hohimer Company Portal - Company/Hohimer Team Shared 4-15-19/compliance/mail/{year}/
  client_base: C:/Users/{username}/Hohimer Wealth Management/Hohimer Company Portal - Company/Hohimer Team Shared 4-15-19/401k Clients/
```
The application resolves these paths at runtime, replacing variables like {username} with the current Windows user and {year} with the appropriate year.

The application will attempt to connect to the database in the following order:
1. Office path (with dynamic username)
2. Home path
3. Fallback path

## Database Connection Management

```python
def get_database_connection():
    # Read paths from YAML config
    config = read_config()
    
    # Try paths in priority order
    paths = [
        config['database']['office'].replace('{username}', os.getlogin()),
        config['database']['home'],
        config['database']['fallback']
    ]
    
    # Try each path until successful
    for path in filter(None, paths):
        try:
            if os.path.exists(path):
                conn = sqlite3.connect(path)
                conn.row_factory = sqlite3.Row
                return conn
        except Exception as e:
            logging.error(f"Failed to connect to {path}: {e}")
    
    raise Exception("Could not connect to any database location")
```

## API Design

The API layer follows a "view-aligned" approach where endpoints map directly to database views:

### Client Endpoints

```python
@router.get("/sidebar", response_model=List[ClientSidebarModel])
def get_client_sidebar():
    """Fetches client sidebar data directly from v_client_sidebar"""
    conn = get_db_connection()
    result = conn.execute("SELECT * FROM v_client_sidebar").fetchall()
    return [ClientSidebarModel(**dict(row)) for row in result]

@router.get("/details/{client_id}", response_model=ClientDetailsModel)
def get_client_details(client_id: int):
    """Fetches comprehensive client data from v_client_details"""
    conn = get_db_connection()
    result = conn.execute(
        "SELECT * FROM v_client_details WHERE client_id = ?", 
        (client_id,)
    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientDetailsModel(**dict(result))
```

### Payment Endpoints

```python
@router.get("/history/{client_id}", response_model=List[PaymentHistoryModel])
def get_payment_history(client_id: int):
    """Fetches payment history from v_payment_history"""
    conn = get_db_connection()
    result = conn.execute(
        "SELECT * FROM v_payment_history WHERE client_id = ?", 
        (client_id,)
    ).fetchall()
    return [PaymentHistoryModel(**dict(row)) for row in result]

@router.post("/create", response_model=PaymentResponseModel)
def create_payment(payment: PaymentCreateModel):
    """Creates a new payment record"""
    conn = get_db_connection()
    with conn:  # Ensures transaction
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
            (payment.contract_id, payment.client_id, payment.received_date, 
             payment.total_assets, payment.actual_fee, payment.method, 
             payment.notes, payment.applied_start_month, payment.applied_start_month_year,
             payment.applied_end_month, payment.applied_end_month_year,
             payment.applied_start_quarter, payment.applied_start_quarter_year,
             payment.applied_end_quarter, payment.applied_end_quarter_year)
        )
        payment_id = cursor.lastrowid
        
        # Handle file attachment if provided
        if payment.file_id:
            cursor.execute(
                "INSERT INTO payment_files(payment_id, file_id, linked_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (payment_id, payment.file_id)
            )
            
    return {"payment_id": payment_id, "success": True}
```

## Document Management

The system uses a dual-location approach for document management:

1. **Primary Storage (Mail Dump)**:
C:/Users/{username}/Hohimer Wealth Management/.../compliance/mail/{year}/
All files are physically stored once in this location.

2. **Client Access (Windows Shortcuts)**:
C:/Users/{username}/Hohimer Wealth Management/.../401k Clients/{client_name}/Consulting Fee/{year}/
Windows shortcuts (.lnk files) in client folders point to the original files in the mail dump.

Variables in paths are resolved at runtime:
- {username}: Current Windows user (from os.getlogin())
- {year}: Appropriate year (current year or extracted from document)
- {client_name}: Client display name from the database

### Document Path Management### Document Path Management

```python
class FileManager:
    def __init__(self, config):
        self.mail_dump_path = config['files']['mail_dump']
        self.client_base_path = config['files']['client_base']
        
    def get_mail_dump_path(self, year=None):
        """Gets the mail dump path for a specific year"""
        if year is None:
            year = datetime.now().year
        path = self.mail_dump_path.replace("{username}", os.getlogin()).replace("{year}", str(year))
        return path
        
    def get_client_shortcut_path(self, client_name, year, filename):
        """Creates a path for a client shortcut file"""
        base = self.client_base_path.replace("{username}", os.getlogin())
        return os.path.join(base, client_name, "Consulting Fee", str(year), filename + ".lnk")
        
    def save_document(self, file_data, filename, document_date=None):
        """Saves document to mail dump and creates database entry"""
        year = datetime.now().year if document_date is None else document_date.year
        mail_path = self.get_mail_dump_path(year)
        os.makedirs(mail_path, exist_ok=True)
        
        full_path = os.path.join(mail_path, filename)
        with open(full_path, 'wb') as f:
            f.write(file_data)
            
        # Create database entry
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO client_files(file_path, original_filename, document_date) VALUES (?, ?, ?)",
            (full_path, filename, document_date or datetime.now().strftime("%Y-%m-%d"))
        )
        file_id = cursor.lastrowid
        conn.commit()
            
        return {"file_id": file_id, "file_path": full_path}
```

## UI Components

The UI follows the blueprint provided in the documentation with these key components:

1. **Client Sidebar**
   - Displays clients with status indicators (PAID/UNPAID)
   - Provides search functionality
   - Toggles between client and provider views

2. **Payment Details View**
   - Shows client information, contract details, and compliance status
   - Displays last payment with variance indicators
   - Lists missing payments

3. **Payment Entry Form**
   - Handles date, period selection, amount, and asset entry
   - Supports split payment toggle
   - Manages file attachments

4. **Payment History Table**
   - Displays payment history with clear variance indicators
   - Supports collapsible split payments
   - Provides document viewing capabilities

5. **Document Viewer**
   - Split-screen interface when viewing attachments
   - Supports PDF/image viewing with zoom capabilities

## Period Reference Maintenance

A background task runs daily to update the period_reference table:

```python
@app.on_event("startup")
async def setup_periodic_tasks():
    @repeat_every(seconds=60*60*24)  # Once a day
    async def update_period_reference():
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
            
    # Start the background task
    asyncio.create_task(update_period_reference())
```

## Development Guidelines

1. **Follow the View-First Approach**
   - Always check if a view already provides the data you need
   - Don't duplicate view logic in application code
   - Let the database handle complex calculations

2. **Component Sizing**
   - Aim to keep components under 200 lines as a guideline
   - Break down components when it improves readability and maintenance
   - Don't artificially split components when it harms cohesion


3. **File Handling Best Practices**
   - Store complete file paths in the database for direct access
   - Create Windows shortcuts (.lnk files) to maintain folder hierarchy
   - Use standardized naming convention for mail dump files
   - Handle document associations through database tables, not filesystem organization
   - Resolve path variables at runtime for portability across user environments

4. **Error Handling**
   - Provide meaningful error messages for file and database operations
   - Implement graceful fallbacks for missing database connections
   - Handle document access issues transparently

## Getting Started

1. **Install Dependencies**
   ```bash
   # Backend
   pip install fastapi uvicorn pydantic python-multipart pyyaml
   
   # Frontend
   npm install react react-dom next tailwindcss shadcn-ui
   ```

2. **Configure Database Paths**
   - Create a `config.yaml` file with appropriate paths
   - Ensure the SQLite database is accessible

3. **Run Development Server**
   ```bash
   # Backend
   uvicorn main:app --reload
   
   # Frontend
   npm run dev
   ```

## Deployment

As a Windows desktop application, deployment involves:
1. Packaging the application with PyInstaller
2. Setting up the configuration file
3. Ensuring OneDrive is configured on target machines
4. Creating desktop shortcuts for easy access

---

# Additional Implementation Details

## Error Logging
```
/logs
  app.log          # Central error log location
```

The application implements focused error logging with:
- Log location: Project directory `/logs/app.log`
- Log level: ERROR (only actionable errors)
- Format: Timestamp, error message, file location, and line number
- Purpose: Debugging support with minimal verbosity

## Database Backup
```python
# Executed daily on application startup
def backup_database():
    """Creates a timestamped backup of the current database"""
    config = read_config()
    current_db_path = get_current_database_path()
    
    # Determine backup location based on environment
    if "office" in current_db_path:
        backup_dir = config['database']['backup']['office'].replace("{username}", os.getlogin())
    else:
        backup_dir = config['database']['backup']['home']
        
    os.makedirs(backup_dir, exist_ok=True)
    backup_filename = f"backup_{datetime.now().strftime('%Y%m%d')}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Create backup
    shutil.copy2(current_db_path, backup_path)
    
    # Retention policy: 7 daily backups + 4 weekly backups
    cleanup_old_backups(backup_dir)
```

## Data Refresh Strategy
- Pull data from database when view is loaded
- Simple manual refresh button in UI
- No automatic background refresh

## File System Access
- Access files directly via standard filesystem operations
- OneDrive synchronization handled by operating system
- Store relative paths in database, construct full paths at runtime

## Initial Application View
- Application launches directly to Payments screen
- No client selection is preserved between sessions



# Testing File Path Management

## Challenge & Solution

The 401(k) Payment Management System relies on accessing files in specific OneDrive locations, which presents challenges when developing or testing outside the work environment. To address this, we implement a configurable file path resolution system that works seamlessly across environments.

## Implementation Approach

The system implements a `FilePathManager` class that:

- Detects whether the application is running in production or development environment
- Uses environment-appropriate base paths from configuration
- Constructs consistent client-specific file paths in either environment
- Provides methods to build and resolve paths for documents

## Testing Configuration

The application includes test-specific path configurations in the YAML config that define:

- Production OneDrive paths (with username placeholders)
- Development/testing paths pointing to local mock directories

## Environment Integration

During development and testing, the system uses a local directory structure that mimics the production OneDrive organization:

```
/test_data
  /mock_onedrive
    /Client1_Name
      /Consulting Fee
        /2024
    /Client2_Name
      /Consulting Fee
        /2024
```

## Testing Strategy

File path handling is tested through:

1. **Unit tests** that verify path construction logic
2. **Integration tests** that confirm file operations work correctly

## Benefits of This Approach

1. **Environment Agnostic**: The same code works in both development and production
2. **Automatic Detection**: The system can auto-detect which environment it's running in
3. **Testable**: File operations can be thoroughly tested without access to OneDrive
4. **Consistent Structure**: Ensures files are organized the same way across environments
5. **Configuration-Driven**: Path structures can be adjusted through configuration

This design allows developers to work on and test file handling functionality regardless of their location or access to the production OneDrive structure, while ensuring consistent behavior when deployed to production.​​​​​​​​​​​​​​​​


# Testing Strategy
 
## Test Database

The application uses a dedicated test database that is a copy of the production database:

```
backend/data/401k_payments_test.db
```

This test database provides several advantages:
- Contains real-world data with all edge cases
- Allows destructive testing without affecting production data
- Maintains consistent test scenarios across development environments

## Configuration

The test configuration automatically selects the test database when running in test mode:

```yaml
database:
  office: C:/Users/{username}/Hohimer Wealth Management/.../401k_payments_66.db
  home: backend/data/401k_payments_66.db
  test: backend/data/401k_payments_test.db
```

## Test Database Maintenance

Before major test runs, refresh the test database:

```bash
# Update test database with latest schema and anonymized data
cp backend/data/401k_payments_66.db backend/data/401k_payments_test.db
```

## Integration with Test Suite

Tests automatically use the test database through the configuration system:

```python
# Tests will use this helper function
def get_test_db_connection():
    """Returns a connection to the test database"""
    return sqlite3.connect("backend/data/401k_payments_test.db")
```

This approach ensures tests run against realistic data while protecting the production database from test operations.