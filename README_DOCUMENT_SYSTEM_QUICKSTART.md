# Document Management System: Quick-Start Guide

## Overview

The 401K Payment Document Management System implements a "Store Once, Link Everywhere" architecture where documents are stored in a central location with shortcuts to client folders. This guide covers basic usage of the system.

## Getting Started

### 1. Processing Existing Documents

To scan an existing mail dump folder for 401K payment documents:

```bash
# Navigate to project root
cd /path/to/OK_401K

# Process current year's documents
python document_processor.py

# OR specify a year
python document_processor.py --year 2024

# See all options
python document_processor.py --help
```

This will:
- Scan the mail dump folder for PDFs
- Identify 401K payment documents
- Extract provider, client, and date information
- Create database entries
- Create shortcuts in client folders
- Link documents to matching payments

### 2. Uploading New Documents

New documents can be uploaded via the API:

```
POST /api/documents/upload

Form data:
- file: File to upload
- client_ids: Array of client IDs to associate with
- payment_ids: (Optional) Array of payment IDs to link to
- provider_id: (Optional) Provider ID
```

This endpoint:
- Saves the document to the mail dump
- Creates database entries
- Creates shortcuts in client folders
- Links the document to payments (if specified)

### 3. Viewing Documents

Documents can be accessed through:

```
# Get all documents for a payment
GET /api/documents/payment/{payment_id}

# Download a specific document
GET /api/documents/{file_id}
```

### 4. Managing Documents

Additional management endpoints:

```
# Link a document to a payment
POST /api/documents/link
{
  "payment_id": 123,
  "file_id": 456
}

# List unprocessed documents
GET /api/documents/unprocessed

# Manually trigger document processing
POST /api/documents/process?year=2025
```

## Configuration

### Path Settings

Document paths are configured in `backend/config.yaml`:

```yaml
files:
  mail_dump: C:/Users/{username}/Hohimer Wealth Management/Hohimer Company Portal - Company/Hohimer Team Shared 4-15-19/compliance/mail/{year}/
  client_base: C:/Users/{username}/Hohimer Wealth Management/Hohimer Company Portal - Company/Hohimer Team Shared 4-15-19/401k Clients/
```

### System Settings

Runtime settings are stored in the `system_config` table:

```sql
-- View settings
SELECT * FROM system_config;

-- Update a setting
UPDATE system_config 
SET config_value = '30' 
WHERE config_key = 'days_to_match_payment';
```

## Document Recognition Patterns

Recognition patterns determine how files are identified and processed. These are stored in the `document_patterns` table and can be updated to handle new formats:

```sql
-- Add a new pattern for identifying 401K documents
INSERT INTO document_patterns (
    pattern_type, pattern, description, priority
) VALUES (
    'document_type', 
    'Retirement Plan Fee', 
    'Alternative naming for 401k documents', 
    5
);
```

## Troubleshooting

### Check Processing Logs

Processing results are stored in the `processing_log` table:

```sql
-- View recent processing logs
SELECT * FROM processing_log ORDER BY process_date DESC LIMIT 20;

-- View errors
SELECT * FROM processing_log WHERE status = 'error';
```

### Unprocessed Documents

Documents that failed processing or weren't recognized:

```sql
-- List unprocessed documents
SELECT * FROM client_files WHERE is_processed = 0;

-- Force processing of all documents
UPDATE client_files SET is_processed = 0;
```

Then run `python document_processor.py` to reprocess.

### Manual Processing

For difficult documents, use the standalone script:

```bash
# Process a specific file
python document_processor.py --file "/path/to/specific/document.pdf"
```

## Scheduled Processing

The system automatically:
- Scans for new documents hourly
- Processes mail dump on application startup
- Creates processing logs for auditing

You can disable automatic processing by updating the config:

```sql
UPDATE system_config 
SET config_value = 'false' 
WHERE config_key = 'enable_autoprocessing';
```
