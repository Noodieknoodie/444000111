# 401k Payment Document Management System

## 1. Core Concept: "Store Once, Link Everywhere"

The document management system follows a simple but powerful principle: each document is stored exactly once in a central location (mail dump), with database links and Windows shortcuts connecting it to all relevant clients and payments.

### Key Benefits
- Eliminates duplicate file storage across client folders
- Creates clear database associations between documents and payments
- Maintains familiar folder structure through Windows shortcuts
- Enables both manual uploads and automated document processing
- Supports multiple clients sharing a single document

## 2. System Architecture

### File Storage Structure
```
[MAIL DUMP]
C:/Users/{username}/Hohimer Wealth Management/.../compliance/mail/{year}/
└── {original_document_files}   # Single source of truth for all documents

[CLIENT FOLDERS]
C:/Users/{username}/Hohimer Wealth Management/.../401k Clients/
└── {client_name}/
    └── Consulting Fee/
        └── {year}/
            └── {shortcut_files.lnk}   # Windows shortcuts pointing to mail dump
```

### Database Structure
```sql
-- Stores document metadata
CREATE TABLE "client_files" (
    "file_id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "file_path" TEXT NOT NULL,         -- Path in mail dump
    "original_filename" TEXT NOT NULL,
    "upload_date" DATETIME DEFAULT CURRENT_TIMESTAMP,
    "document_date" TEXT,              -- Date from document
    "provider_id" INTEGER,             -- From providers table
    "is_processed" INTEGER DEFAULT 0,  -- Shortcut creation flag
    "metadata" TEXT                    -- JSON additional data
);

-- Links documents to payments (many-to-many)
CREATE TABLE "payment_files" (
    "payment_id" INTEGER NOT NULL,
    "file_id" INTEGER NOT NULL,
    "linked_at" DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY ("payment_id", "file_id"),
    FOREIGN KEY ("payment_id") REFERENCES "payments" ("payment_id") ON DELETE CASCADE,
    FOREIGN KEY ("file_id") REFERENCES "client_files" ("file_id") ON DELETE CASCADE
);

-- Normalized provider information
CREATE TABLE "providers" (
    "provider_id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "provider_name" TEXT NOT NULL UNIQUE,
    "name_variants" TEXT,              -- Comma-separated list of alternate names/abbreviations
    "valid_from" DATETIME DEFAULT CURRENT_TIMESTAMP,
    "valid_to" DATETIME                -- For soft delete consistency with other tables
);

-- Document pattern recognition
CREATE TABLE "document_patterns" (
    "pattern_id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "pattern_type" TEXT NOT NULL,
    "pattern" TEXT NOT NULL,
    "description" TEXT,
    "priority" INTEGER DEFAULT 1,
    "is_active" INTEGER DEFAULT 1
);

-- System configuration
CREATE TABLE "system_config" (
    "config_key" TEXT PRIMARY KEY,
    "config_value" TEXT NOT NULL,
    "description" TEXT,
    "last_updated" DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Processing log
CREATE TABLE "processing_log" (
    "log_id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "file_name" TEXT NOT NULL,
    "process_date" DATETIME DEFAULT CURRENT_TIMESTAMP,
    "status" TEXT NOT NULL, -- 'processed', 'error', 'skipped'
    "details" TEXT,         -- Error messages or processing notes
    "file_id" INTEGER,      -- Link to client_files if processed
    FOREIGN KEY ("file_id") REFERENCES "client_files" ("file_id")
);
```

### Database Views
```sql
-- Main document view for API and frontend
CREATE VIEW DocumentView AS
SELECT 
    -- Document information
    cf.file_id,
    cf.file_path,
    cf.original_filename,
    cf.document_date,
    cf.is_processed,
    
    -- Provider information
    pr.provider_id,
    pr.provider_name,
    
    -- Payment information
    pf.payment_id,
    p.received_date AS payment_date,
    p.actual_fee,
    
    -- Client information
    c.client_id,
    c.display_name AS client_name
FROM 
    client_files cf
LEFT JOIN 
    providers pr ON cf.provider_id = pr.provider_id
LEFT JOIN 
    payment_files pf ON cf.file_id = pf.file_id
LEFT JOIN 
    payments p ON pf.payment_id = p.payment_id
LEFT JOIN 
    clients c ON p.client_id = c.client_id;
```

## 3. Core Workflows

### Manual Document Upload
1. User uploads document through the application interface
2. System saves the document to the mail dump folder
3. System extracts document metadata (provider, date, client list)
4. User confirms client associations and selects related payments
5. System creates database entries in client_files and payment_files
6. Windows shortcuts are generated in client folders

### Automated Document Processing
1. Background service scans mail dump folder for new documents
2. System analyzes filenames to extract provider, date, and client information
3. Provider and client names are matched to database records using name_variants
4. System identifies relevant payments based on date and client information
5. Database associations are created automatically
6. Windows shortcuts are generated for each associated client

## 4. Document Recognition Logic

### Filename Analysis
The system recognizes documents using patterns stored in the database, which can be easily updated:

```sql
-- Example patterns in document_patterns table
INSERT INTO document_patterns (pattern_type, pattern, description, priority)
VALUES ('document_type', '401[kK] Advisor Fee', '401k payment documents', 10);

INSERT INTO document_patterns (pattern_type, pattern, description, priority)
VALUES ('provider_pattern', '^([^-]+) -', 'Provider name is typically before first dash', 10);

INSERT INTO document_patterns (pattern_type, pattern, description, priority) 
VALUES ('client_list_pattern', '401[kK] Advisor Fee[s]? - ([^-]+)', 'Client list after "401k Advisor Fee -"', 10);

INSERT INTO document_patterns (pattern_type, pattern, description, priority)
VALUES ('date_pattern', '([0-9]{1,2}\\.[0-9]{1,2}\\.[0-9]{2,4})', 'Standard date format (MM.DD.YY)', 10);
```

### Payment Association
For each identified client, the system finds relevant payments by:
1. Matching the client_id from the identified client name (including variants)
2. Matching the provider_id from the identified provider (including variants)
3. Finding payments with dates near the document date (configurable matching window)
4. Creating associations in the payment_files table

## 5. Technical Components

### Path Resolver
Handles all file path operations:
- Resolves mail dump path with username and year variables
- Creates client folder paths for shortcuts
- Generates Windows shortcuts between mail dump and client folders

### File Manager
Handles core file operations:
- Saves documents to mail dump
- Creates database entries
- Integrates with path resolver for shortcut creation

### Document Processor
Handles automated document recognition:
- Scans mail dump for new files
- Uses patterns from database to extract metadata
- Matches providers and clients using name variants
- Creates associations and shortcuts

### Scheduled Tasks
- Hourly task to scan for new documents
- Records processing results in log table

## 6. API Endpoints

```
# Upload and Process
POST /api/documents/upload              # Upload document with client/payment associations
POST /api/documents/process             # Manually trigger document processing

# Retrieval
GET /api/documents/payment/{payment_id} # Get documents for a payment
GET /api/documents/{file_id}            # Download specific document

# Management
POST /api/documents/link                # Link document to payment
GET /api/documents/unprocessed          # Get unprocessed documents
```

## 7. Utilities

### Standalone Document Processor
A command-line utility (`document_processor.py`) for:
- Processing documents for a specific year
- Processing a single file
- Listing unprocessed documents

```bash
# Process current year documents
python document_processor.py

# Process documents for a specific year
python document_processor.py --year 2024

# Process a specific file
python document_processor.py --file "/path/to/document.pdf"

# List unprocessed documents
python document_processor.py --list-unprocessed
```

## 8. Implementation Notes

### Client and Provider Name Variants
The system can handle variations in client and provider names:

```sql
-- Provider name variants
UPDATE providers SET name_variants = 'JH' WHERE provider_name = 'John Hancock';
UPDATE providers SET name_variants = 'Prin' WHERE provider_name = 'Principal';

-- Client name variants
UPDATE clients SET name_variants = 'FF,FlorForm,Floform Countertops' WHERE display_name = 'Floform';
UPDATE clients SET name_variants = '3Sig,3 Sigma,3S' WHERE display_name = 'Three Sigma';
```

### Storage Strategy
- Original files are stored with their original filenames in the mail dump
- Full paths are stored in the database for direct access
- The year is extracted from the filename to determine the appropriate mail dump subfolder
- Shortcuts preserve the appearance of files being in client folders

### Configuration
System settings are stored in:
1. `config.yaml` - Basic path templates
2. `system_config` table - Runtime configuration that can be updated through the application

This approach ensures consistency, security, and proper handling of file paths across different Windows environments.
