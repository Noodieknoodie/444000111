# 401(k) PAYMENT MANAGEMENT SYSTEM BLUEPRINT

## PROJECT OVERVIEW

This blueprint outlines the development of a 401(k) payment management system - an internal tool for a company that oversees investment plans on behalf of client organizations. The system's primary purpose is to track, manage, and store incoming payments from investment providers like John Hancock, replacing an outdated Excel-based tracking method. The system is designed with simplicity in mind, utilizing the power of SQLite views to handle complex business logic directly in the database. This approach minimizes application code and ensures consistent calculations and business rules throughout the system. Designed specifically for simplicity, the app operates on local servers, uses direct SQLite queries, and intentionally excludes advanced security measures or authentication mechanisms. All employees share a common file structure, with the only variation being the unique USER PROFILE path in their respective file systems.

Key functionality includes:
- Payment tracking and compliance monitoring
- Document storage and retrieval
- Payment history and reporting
- Fee calculation and variance analysis
- Client portfolio management
- more to come

The foundation of this system is a sophisticated SQLite database featuring extensive views that handle most business logic. This architecture offloads complex calculations, period tracking, and compliance checks to the database layer, significantly simplifying the application code.

For detailed database information, reference `README_DATABASE.md`, which contains the complete schema documentation, including tables, views, and indexes.

### Key Database Features

1. **Business Logic in Views**: Complex calculations, date handling, and compliance checks are implemented directly in database views.
2. **Soft Delete Pattern**: All major tables support soft deletion via the `valid_to` field.
3. **Comprehensive UI Views**: Dedicated views provide pre-formatted data for specific frontend components.
4. **Period Calculations**: Sophisticated handling of monthly and quarterly periods with built-in arrears logic.
5. **Variance Analysis**: Automatic calculation of payment variance with tolerance-based classification.

**note: need to have a function in place to keep the "period_reference" table up to date. The logic is: todays date is the reference date. Remember, areers logic... today's month minus 1 is the current_month. today's month minus 3 is the current quarter. areers applies to both monthly and quarterly as a single intiger "lookback" period depending on the period type. 

-- period_reference
CREATE TABLE period_reference (
    reference_date TEXT PRIMARY KEY,
    current_month_year INTEGER,
    current_month INTEGER,
    current_quarter_year INTEGER,
    current_quarter INTEGER
);

## DEVELOPMENT "VIBE" & THE AGENT'S (you) ROLE AND DUTY

### Code Standards & Approach
The code should be written with a focus on maintainability and clarity. This is a small internal tool for about 5 people in a company, so we prioritize straightforward, readable code over advanced optimizations or enterprise-level architecture.

### Comments & Documentation
Code comments should focus less on explaining what something does and more on HOW IT'S USED, which areas, files, or functions use it, and why it's important. This helps future agents understand what's going on and prevents logic duplication.

### Future Development Considerations
This project will only be built by AI code agents, so tailor the code for FUTURE AGENTS who will pick up where you left off. Leave breadcrumbs in the form of clear comments, consistent naming conventions, and logical file organization.

### Code Principles
- Keep the code lightweight and prevent feature creep
- Use descriptive, consistent naming for variables and functions
- Aim for less code, not more - simplicity is preferred
- Leverage database views whenever possible instead of duplicating logic in code
- Create reusable utilities for common operations

### Agent Initiative
Take FULL initiative to: CREATE NEW FILES / REMOVE FILES / REMOVE ORPHANED CODE / REMOVE DUPLICATED LOGIC whenever you come across it. Your job is to maintain the ENTIRE PROJECT AS A WHOLE, not just focus on individual sections.

### Problem-Solving Approach
Be clever and use constants or other files or functions to assist in repetitive tasks. Don't reinvent the wheel - check if the database views already handle the logic you're considering implementing.

### CRITICAL
Always use chain of thought reasoning and look at MORE CODE FILES THAN YOU THINK to develop EXCESSIVE CONTEXT about the project and current code before implementing anything. Most importantly, ALWAYS PROVE TO ME the plan of action before doing anything. ALWAYS ASK FOR PERMISSION BEFORE CODING.

If any edge cases become apparent during the process, please disclose them to me and explain your reasoning so that we can discuss them.


** SPLIT PAYMENT LOGIC EXPLAINED **
- Split payments are payments that cover multiple periods.
- They are entered as a single payment record in the database.
- they are identified by having a different applied period end than recieved 
- split payments are treated as single payments only for identifying missed payments... 
- split payments are not treated as multiple single payments for purposes of calculating expected fees, etc.
- if a payment is split, expected fees, variance, etc. are muted entirely for simplicity. 
- the logic regarding how the split occurs behind the scenes is simple:  the payment amount is divided and applied equally by the number of periods covered by the payment. 
- a db view is used to map payments to periods.
- another view identifies any missing periods not covered. 
- we do not need to get ultra-granular 

---


## BACKEND IMPLEMENTATION


// PLEASE CHECK TO ENSURE THAT NO UPDATES HAVE SINCE OCCURED IN THE SCHEMA FILES BEFORE PROCEEDING - THERE MIGHT BE A NEW VIEW THAT COULD MAKE YOUR JOB EASIER

The backend serves as a thin API layer that primarily passes data between the database views and the frontend.

### Directory Structure

```
/backend
  /services       # Database access services
  /helpers        # Utility functions
  /routes         # API endpoint definitions
  /config         # Configuration settings
  /data           # Database and file storage
  main.py         # App entry point
```

### Core Helper Functions

1. **Database Connection**
   ```python
   def get_db_connection():
       """
       Establishes connection to SQLite database with proper settings.
       Returns connection with row factory set to return dictionaries.
       
       Used by all service functions requiring database access.
       """
   ```

2. **File Path Resolution**
   ```python
   def resolve_file_path(relative_path, username=None):
       """
       Converts relative OneDrive paths to absolute file system paths.
       Handles username substitution for different environments.
       
       Used by file upload/download operations.
       """
   ```

3. **Standard Response Formatter**
   ```python
   def format_response(data, status="success", pagination=None):
       """
       Creates standardized API response structure.
       Adds pagination metadata when provided.
       
       Used by all API route handlers to ensure consistent responses.
       """
   ```

### Services Layer

1. **Client Service**
   ```python
   def get_clients(search=None, provider=None, status=None):
       """
       Retrieves client list with optional filtering.
       Uses vw_ui_client_selector view directly.
       """
   
   def get_client_details(client_id):
       """
       Gets comprehensive client information including
       contracts and contact details from vw_ui_client_details.
       """
   ```

2. **Payment Service**
   ```python
   def get_client_dashboard(client_id):
       """
       Retrieves dashboard data for a client directly from
       vw_ui_client_dashboard view without additional processing.
       """
       
   def get_payment_history(client_id, year=None, limit=10, offset=0):
       """
       Gets paginated payment history from vw_ui_payment_history
       with optional year filtering.
       """
   
   def create_payment(payment_data):
       """
       Creates new payment record with proper period data.
       Form default values come from vw_ui_payment_form_defaults.
       """
   
   def get_payment(payment_id):
       """
       Retrieves detailed payment information
       including linked documents.
       """
   ```

3. **Document Service**
   ```python
   def upload_file(file, client_id, payment_id=None):
       """
       Handles file upload to appropriate OneDrive location and
       creates database entries.
       """
   
   def get_client_documents(client_id):
       """
       Retrieves all documents for a client from
       vw_ui_document_list view.
       """
   
   def get_document(file_id):
       """
       Retrieves document content and metadata.
       """
   ```

4. **Compliance Service**
   ```python
   def get_compliance_status():
       """
       Retrieves overall compliance status for all clients
       directly from vw_ui_client_compliance.
       """
       
   def get_missing_periods(client_id):
       """
       Retrieves missing payment periods for a client
       directly from vw_ui_missing_periods.
       """
   ```

### API Routes

1. **Client Routes**
   - `GET /api/clients` - List clients with filtering
   - `GET /api/clients/{client_id}` - Get detailed client info
   - `GET /api/clients/{client_id}/dashboard` - Get dashboard data

2. **Payment Routes**
   - `GET /api/payments/{client_id}` - Get payment history
   - `POST /api/payments` - Create new payment
   - `PUT /api/payments/{payment_id}` - Update payment 
   - `DELETE /api/payments/{payment_id}` - Soft delete payment
   - `GET /api/payment-form-defaults/{client_id}/{contract_id}` - Get form defaults

3. **Document Routes**
   - `POST /api/documents` - Upload new document
   - `GET /api/documents/{file_id}` - Get document content
   - `GET /api/clients/{client_id}/documents` - List client documents
   - `POST /api/payments/{payment_id}/link-document/{file_id}` - Link document to payment

4. **Compliance Routes**
   - `GET /api/compliance` - Get overall compliance status
   - `GET /api/clients/{client_id}/missing-periods` - Get missing periods

## FRONTEND IMPLEMENTATION

The frontend provides an intuitive interface that directly consumes the data provided by the database views through the API.

### Directory Structure

```
/frontend
  /components
    /layout        # Layout components
    /dashboard     # Dashboard components
    /payments      # Payment management components
    /documents     # Document handling components
    /shared        # Reusable UI components
  /pages           # Page components
  /hooks           # Custom React hooks
  /services        # API service calls
  /utils           # Utility functions
  /context         # Shared state management
  /styles          # Global styles
```

### Key Components

1. **Client Selection Sidebar**
   ```jsx
   // Displays clients with compliance indicators
   // Directly uses data from vw_ui_client_selector
   // Provides filtering by client name or provider
   <ClientSidebar
     clients={clients}
     activeClient={selectedClientId}
     onClientSelect={handleClientSelect}
   />
   ```

2. **Dashboard Summary**
   ```jsx
   // Shows payment status and contract details
   // Uses data from vw_ui_client_dashboard
   // Displays compliance status and latest payment
   <DashboardSummary
     clientData={dashboardData}
     onAddPayment={handleAddPayment}
     onViewHistory={handleViewHistory}
   />
   ```

3. **Payment Form**
   ```jsx
   // Form for adding/editing payments
   // Gets defaults from vw_ui_payment_form_defaults
   // Includes file upload functionality
   <PaymentForm
     clientId={clientId}
     contractId={contractId}
     onSubmit={handlePaymentSubmit}
     initialValues={formDefaults}
   />
   ```

4. **Payment History Table**
   ```jsx
   // Displays payment history with filtering
   // Directly uses data from vw_ui_payment_history
   // Shows variance indicators and document links
   <PaymentHistoryTable
     payments={payments}
     onRowClick={handlePaymentSelect}
     onEditPayment={handleEditPayment}
   />
   ```

5. **Document Viewer**
   ```jsx
   // Displays document content and metadata
   // Handles download functionality
   // Shows payment linkage information
   <DocumentViewer
     documentId={selectedDocumentId}
     metadata={documentMetadata}
     onClose={handleCloseViewer}
   />
   ```

6. **Compliance Dashboard**
   ```jsx
   // Overview of client compliance status
   // Uses data from vw_ui_client_compliance
   // Shows missing periods and payment status
   <ComplianceDashboard
     complianceData={complianceStatus}
     onClientSelect={handleClientSelect}
   />
   ```

### Frontend Services

1. **Client Service**
   ```jsx
   // API calls related to clients
   const fetchClients = async (search, provider) => {
     // Gets data from API backed by vw_ui_client_selector
   };
   
   const fetchClientDetails = async (clientId) => {
     // Gets data from API backed by vw_ui_client_details
   };
   ```

2. **Payment Service**
   ```jsx
   // API calls related to payments
   const fetchClientDashboard = async (clientId) => {
     // Gets data from API backed by vw_ui_client_dashboard
   };
   
   const fetchPaymentHistory = async (clientId, year) => {
     // Gets data from API backed by vw_ui_payment_history
   };
   
   const createPayment = async (paymentData) => {
     // Posts data using defaults from vw_ui_payment_form_defaults
   };
   ```

3. **Document Service**
   ```jsx
   // API calls related to documents
   const uploadDocument = async (file, clientId, paymentId) => {
     // Handles file upload with appropriate metadata
   };
   
   const fetchClientDocuments = async (clientId) => {
     // Gets data from API backed by vw_ui_document_list
   };
   ```

## IMPLEMENTATION ROADMAP

### Phase 1: Database Setup and API Foundation

1. Create SQLite database with all tables and indexes
2. Implement core database views (period utils, payment base)
3. Build backend infrastructure with FastAPI
4. Develop basic API endpoints for clients and contracts
5. Create file handling utilities and document endpoints

### Phase 2: Core Payment Functionality

1. Implement payment-related database views
2. Develop payment creation and history endpoints
3. Build form default logic and expected fee calculations
4. Create payment variance analysis views
5. Implement document linking functionality

### Phase 3: Frontend Core Components

1. Set up Next.js project with Tailwind CSS
2. Create layout and navigation components
3. Build client selection sidebar
4. Develop dashboard summary components
5. Implement basic forms for client and payment data

### Phase 4: Advanced Features and Integration

1. Implement compliance tracking views and endpoints
2. Build document management interface
3. Create payment history and filtering components
4. Develop split payment interface and logic
5. Implement search and filtering functionality

### Phase 5: Refinement and QA

1. Optimize database queries and add needed indexes
2. Implement comprehensive error handling
3. Add validation and data integrity checks
4. Test all functionality across different environments
5. Fine-tune UI for improved user experience

## CODE MAINTENANCE AND FUTURE DEVELOPMENT

### Documentation Standards

- Comment why code exists and how it's used rather than what it does
- Document database view usage for each component
- Maintain a centralized list of view-to-component relationships
- Include SQL queries directly in comments for clarity

### Testing Strategy

- Focus on integration tests rather than unit tests
- Test database views directly for data integrity
- Validate calculations match expected outcomes
- Ensure consistent behavior across environments

### Future Considerations

- Database backup and restore functionality
- Reporting and export capabilities
- User preferences for default views
- Enhanced search and filtering options
- Historical analysis of fee trends

## BEST PRACTICES

### When Creating New Code

1. Always check if a database view already provides the needed functionality
2. Use consistent naming that matches database field names
3. Handle null values and edge cases deliberately
4. Document the relationship between UI components and database views
5. Prefer query parameters over custom SQL when possible

### Code Examples

Good example (leveraging database views):
```python
def get_client_dashboard(client_id):
    conn = get_db_connection()
    result = conn.execute(
        "SELECT * FROM vw_ui_client_dashboard WHERE client_id = ?",
        (client_id,)
    ).fetchall()
    conn.close()
    return result
```

Bad example (duplicating logic):
```python
def get_client_dashboard(client_id):
    # DON'T DO THIS - duplicates logic from database views
    conn = get_db_connection()
    client = conn.execute("SELECT * FROM clients WHERE client_id = ?", (client_id,)).fetchone()
    payments = conn.execute("SELECT * FROM payments WHERE client_id = ?", (client_id,)).fetchall()
    last_payment = get_most_recent_payment(payments)  # Unnecessary logic
    # Manual calculations that are already done in views
    compliance_status = calculate_compliance(last_payment)  # Duplicated logic
    conn.close()
    return {"client": client, "last_payment": last_payment, "compliance": compliance_status}
```

By following this blueprint, you will create a maintainable, efficient system that leverages the power of database views while keeping application code clean and minimal.