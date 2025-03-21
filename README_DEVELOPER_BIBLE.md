# THE 401(k) PAYMENT MANAGEMENT SYSTEM - DEVELOPER'S BIBLE

## INTRODUCTION: WHY THIS SYSTEM EXISTS & WHAT IT DOES

This is an internal tool for a small company (about 5 people) that manages 401(k) plans for client businesses. They're replacing a shitty Excel system with this app. The system handles:

1. Tracking client payments for 401(k) management services
2. Detecting missed payments 
3. Calculating expected fees and variances
4. Storing documents related to payments
5. Generating reports

**ESSENTIAL BUSINESS CONTEXT**: They get paid for managing these 401(k) plans AFTER the period ends (in arrears). Monthly clients pay for the previous month, quarterly clients pay for the previous quarter. So if today is Feb 20, 2028, they're collecting for Jan 2028 (monthly clients) or Q4 2027 (quarterly clients).

**THE BIG IDEA**: Almost all complex business logic is in SQLite views. This is INTENTIONAL. The views handle all the complexity of figuring out periods, calculating fees, determining payment status, etc. The app code should be fairly thin, mostly connecting the UI to the right views. DON'T DUPLICATE VIEW LOGIC IN APPLICATION CODE!

## CORE DESIGN PRINCIPLES

1. **DB Views Do The Heavy Lifting**: If you think "I need to calculate X" - FIRST check if a view already does it.
2. **Soft Delete Everything**: All primary tables use `valid_to IS NULL` for active records.
3. **Split Payments Are Special**: NEVER treat split payments as multiple payments - they're always ONE payment covering multiple periods.
4. **First Payment Is The Truth**: NEVER trust manual date fields like `ima_signed_date` to determine when a client relationship started. Instead, use their first recorded payment date.
5. **Estimated Values Are Clearly Marked**: For percentage-based fees where AUM is missing, estimated values ALWAYS have a flag field marking them as estimates.

## DATA MODEL FUNDAMENTALS

### THE BILLING MODEL

There are TWO dimensions that determine how a client is billed:

1. **Schedule**: Either "monthly" or "quarterly"
2. **Fee Type**: Either "percentage" (of assets) or "flat" (fixed amount)

So four possible combinations:
- Monthly percentage (e.g., 0.0007 of assets monthly)
- Monthly flat (e.g., $666.66 monthly)
- Quarterly percentage (e.g., 0.001875 of assets quarterly)
- Quarterly flat (e.g., $3500 quarterly)

### PAYMENTS & PERIODS

- Payments are stored exactly as received (no modifications)
- Each payment has fields clearly identifying what period(s) it covers:
  - Monthly: `applied_start_month`, `applied_start_month_year`, `applied_end_month`, `applied_end_month_year`
  - Quarterly: `applied_start_quarter`, `applied_start_quarter_year`, `applied_end_quarter`, `applied_end_quarter_year`

- **SUPER IMPORTANT**: Most payments cover a single period (start=end), but "split payments" cover multiple periods. THESE ARE DETECTED BY `applied_start` != `applied_end`.

### PERIOD ENCODINGS

There are TWO period encoding systems:
1. Monthly periods: encoded as `YYYYMM` (year * 100 + month)
2. Quarterly periods: encoded as `YYYYQ` (year * 10 + quarter)

For example:
- January 2025 = 202501
- Q3 2024 = 20243

**REMEMBER**: This encoding is used extensively in the views - don't reinvent period handling!

## THE VIEW ARCHITECTURE

The views are built in tiers, each building on the previous:

1. **Foundation Views**: Handle period calculations and payment expansion
2. **Business Logic Views**: Calculate expected fees, variances, missing payments
3. **UI Views**: Ready-to-use data for specific UI components
4. **Estimation Views**: Provide fee estimates for missing AUM data

## TABLE & VIEW DOCUMENTATION

### CORE TABLES

#### clients
The primary entity - each row represents a client company.
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Primary key |
| display_name | TEXT | Name shown in UI |
| full_name | TEXT | Legal entity name |
| ima_signed_date | TEXT | Contract signature date (UNRELIABLE - use first payment date instead) |
| onedrive_folder_path | TEXT | Path to client docs |
| valid_from | DATETIME | Record creation date |
| valid_to | DATETIME | Soft delete date (NULL for active) |

#### contracts
Defines the billing arrangement with each client.
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| contract_id | INTEGER | Primary key |
| client_id | INTEGER | Foreign key to clients |
| contract_number | TEXT | Provider contract ID |
| provider_name | TEXT | Provider (e.g., "John Hancock") |
| contract_start_date | TEXT | When contract began |
| fee_type | TEXT | Either "percentage" or "flat" |
| percent_rate | REAL | Decimal rate (e.g., 0.0007 = 0.07%) |
| flat_rate | REAL | Fixed amount per period |
| payment_schedule | TEXT | Either "monthly" or "quarterly" |
| num_people | INTEGER | Participants count |
| valid_from | DATETIME | Record creation date |
| valid_to | DATETIME | Soft delete date (NULL for active) |
| is_active | INTEGER | 1 for active, 0 for inactive |

#### payments
Raw payment records exactly as received.
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| payment_id | INTEGER | Primary key |
| contract_id | INTEGER | Foreign key to contracts |
| client_id | INTEGER | Foreign key to clients |
| received_date | TEXT | When payment was received |
| total_assets | INTEGER | Assets under management (NULL for flat fee or missing) |
| actual_fee | REAL | Payment amount received |
| method | TEXT | Payment method (e.g., "Check") |
| notes | TEXT | Additional information |
| valid_from | DATETIME | Record creation date |
| valid_to | DATETIME | Soft delete date (NULL for active) |
| applied_start_month | INTEGER | First month covered (1-12) |
| applied_start_month_year | INTEGER | Year of first month covered |
| applied_end_month | INTEGER | Last month covered (1-12) |
| applied_end_month_year | INTEGER | Year of last month covered |
| applied_start_quarter | INTEGER | First quarter covered (1-4) |
| applied_start_quarter_year | INTEGER | Year of first quarter covered |
| applied_end_quarter | INTEGER | Last quarter covered (1-4) |
| applied_end_quarter_year | INTEGER | Year of last quarter covered |

#### period_reference
Defines the current billing period. CRITICAL TABLE - must be kept up to date.
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| reference_date | TEXT | Primary key, represents current date |
| current_month_year | INTEGER | Year to bill for monthly clients |
| current_month | INTEGER | Month to bill for monthly clients (1-12) |
| current_quarter_year | INTEGER | Year to bill for quarterly clients |
| current_quarter | INTEGER | Quarter to bill for quarterly clients (1-4) |

#### contacts
Stores contact information for clients and providers.
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| contact_id | INTEGER | Primary key |
| client_id | INTEGER | Foreign key to clients |
| contact_type | TEXT | E.g., "Primary", "Authorized", "Provider" |
| contact_name | TEXT | Person's name |
| phone | TEXT | Contact number |
| email | TEXT | Email address |
| fax | TEXT | Fax number |
| physical_address | TEXT | Street address |
| mailing_address | TEXT | Mailing address if different |
| valid_from | DATETIME | Record creation date |
| valid_to | DATETIME | Soft delete date (NULL for active) |

#### client_files
Stores file metadata for client documents.
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| file_id | INTEGER | Primary key |
| client_id | INTEGER | Foreign key to clients |
| file_name | TEXT | Original filename |
| onedrive_path | TEXT | Path in OneDrive |
| uploaded_at | DATETIME | When file was uploaded |

#### payment_files
Links payments to their supporting documents.
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| payment_id | INTEGER | Foreign key to payments |
| file_id | INTEGER | Foreign key to client_files |
| linked_at | DATETIME | When the link was created |

### FOUNDATION VIEWS

#### v_current_period
Pulls the most recent period reference data.
- **Purpose**: Single source of truth for current billing period
- **Why It Exists**: Prevents having to find the latest period in multiple places
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| reference_date | TEXT | Current reference date |
| monthly_year | INTEGER | Current year for monthly billing |
| monthly_month | INTEGER | Current month for monthly billing (1-12) |
| quarterly_year | INTEGER | Current year for quarterly billing |
| quarterly_quarter | INTEGER | Current quarter for quarterly billing (1-4) |

#### v_active_contracts
Filters for active contracts only.
- **Purpose**: Removes soft-deleted contracts for all other views
- **Why It Exists**: Keeps contract filtering consistent
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| (all fields from contracts) | | Only includes records where valid_to IS NULL and is_active = 1 |

#### v_monthly_periods
Generates timeline of all months from first payment to current.
- **Purpose**: Creates continuous sequence of periods for monthly clients
- **Why It Exists**: Forms the foundation for missing payment detection
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| year | INTEGER | Period year |
| month | INTEGER | Period month (1-12) |
| period_key | INTEGER | Encoded period (YYYYMM format) |

#### v_quarterly_periods
Generates timeline of all quarters from first payment to current.
- **Purpose**: Creates continuous sequence of periods for quarterly clients
- **Why It Exists**: Forms the foundation for missing payment detection
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| year | INTEGER | Period year |
| quarter | INTEGER | Period quarter (1-4) |
| period_key | INTEGER | Encoded period (YYYYQ format) |

#### v_all_periods
Combines monthly and quarterly periods into a unified timeline.
- **Purpose**: Single interface for all period types
- **Why It Exists**: Allows common logic to work with both period types
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| year | INTEGER | Period year |
| month | INTEGER | Period month (1-12, NULL for quarterly) |
| quarter | INTEGER | Period quarter (1-4, NULL for monthly) |
| schedule_type | TEXT | Either "monthly" or "quarterly" |
| period_key | INTEGER | Encoded period (YYYYMM or YYYYQ format) |

#### v_client_first_payment
Determines the true start date for each client.
- **Purpose**: Provides reliable client tenure data
- **Why It Exists**: `ima_signed_date` is often NULL or inconsistent
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| display_name | TEXT | Client name |
| first_payment_date | TEXT | Date of first recorded payment |
| client_days | REAL | Days since first payment |
| client_since_formatted | TEXT | Formatted date (MM/DD/YYYY) |

#### v_payments_expanded
Expands split payments across covered periods.
- **Purpose**: Turns a single split payment into multiple period records
- **Why It Exists**: Critical for proper period coverage tracking
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| payment_id | INTEGER | Payment identifier |
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| received_date | TEXT | When payment was received |
| total_assets | INTEGER | AUM amount |
| period_fee | REAL | Fee allocated to this period |
| total_fee | REAL | Total payment amount |
| year | INTEGER | Period year |
| month | INTEGER | Period month (NULL for quarterly) |
| quarter | INTEGER | Period quarter (NULL for monthly) |
| schedule_type | TEXT | Either "monthly" or "quarterly" |
| period_key | INTEGER | Encoded period |
| is_split | INTEGER | 1 if split payment, 0 if not |
| start_period_key | INTEGER | First period covered |
| end_period_key | INTEGER | Last period covered |
| periods_covered | INTEGER | Number of periods in split |

### BUSINESS LOGIC VIEWS

#### v_client_aum_history
Tracks client AUM history and provides estimates for missing data.
- **Purpose**: Supports estimation for percentage-based clients with missing AUM
- **Why It Exists**: Many percentage-based clients have missing AUM data
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| year | INTEGER | Period year |
| month | INTEGER | Period month (NULL for quarterly) |
| quarter | INTEGER | Period quarter (NULL for monthly) |
| schedule_type | TEXT | Either "monthly" or "quarterly" |
| period_key | INTEGER | Encoded period |
| actual_aum | INTEGER | Actual AUM (NULL if missing) |
| estimated_aum | INTEGER | Estimated AUM (based on most recent) |
| is_estimated_aum | INTEGER | 1 if estimated, 0 if actual |

#### v_expected_fees
Calculates expected fees based on contract terms and actual AUM.
- **Purpose**: Determines what each payment should have been
- **Why It Exists**: Forms the foundation for variance analysis
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| year | INTEGER | Period year |
| month | INTEGER | Period month (NULL for quarterly) |
| quarter | INTEGER | Period quarter (NULL for monthly) |
| schedule_type | TEXT | Either "monthly" or "quarterly" |
| period_key | INTEGER | Encoded period |
| fee_type | TEXT | Either "percentage" or "flat" |
| percent_rate | REAL | Percentage rate as decimal |
| flat_rate | REAL | Fixed fee amount |
| assets_under_management | INTEGER | Actual AUM |
| expected_fee | REAL | Calculated expected fee |
| payment_id | INTEGER | Payment ID (NULL if missing) |
| actual_fee | REAL | Actual fee received |
| is_split | INTEGER | 1 if split payment, 0 if not |

#### v_expected_fees_with_estimates
Extends expected fees with estimates for missing AUM.
- **Purpose**: Provides estimated fees for percentage clients with missing AUM
- **Why It Exists**: Gives more complete fee data while clearly marking estimates
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| (all fields from v_expected_fees) | | |
| estimated_aum | INTEGER | Estimated AUM from history |
| is_estimated_aum | INTEGER | 1 if AUM is estimated |
| estimated_expected_fee | REAL | Fee calculated with estimated AUM |
| is_estimated_fee | INTEGER | 1 if fee is estimated |

#### v_payment_variance
Calculates and classifies payment variances.
- **Purpose**: Identifies overpayments, underpayments, etc.
- **Why It Exists**: Critical business KPI for monitoring payment accuracy
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| (all fields from v_expected_fees) | | |
| variance_amount | REAL | Difference (actual - expected) |
| variance_percentage | REAL | Percentage difference |
| variance_classification | TEXT | "Within Target", "Overpaid", or "Underpaid" |

#### v_payment_variance_with_estimates
Extends variance analysis with estimated data.
- **Purpose**: Provides variance estimates when AUM is missing
- **Why It Exists**: Gives more complete variance data while marking estimates
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| (all fields from v_expected_fees_with_estimates) | | |
| variance_amount | REAL | Difference using estimated fee |
| variance_percentage | REAL | Percentage difference using estimates |
| variance_classification | TEXT | Classification using estimates |
| is_estimated_fee | INTEGER | 1 if using estimated fees |

#### v_payment_status
Determines if each client has paid for current period.
- **Purpose**: Shows PAID/UNPAID status for current period
- **Why It Exists**: Primary compliance indicator for monitoring
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| display_name | TEXT | Client name |
| payment_schedule | TEXT | Either "monthly" or "quarterly" |
| current_year | INTEGER | Current year to bill |
| current_month | INTEGER | Current month to bill (NULL for quarterly) |
| current_quarter | INTEGER | Current quarter to bill (NULL for monthly) |
| current_period_key | INTEGER | Encoded current period |
| payment_status | TEXT | "PAID" or "UNPAID" |
| formatted_current_period | TEXT | Human-readable period (e.g., "Jan 2025" or "Q4 2024") |

#### v_missing_payments
Identifies all periods without payments.
- **Purpose**: Shows missing payments for compliance tracking
- **Why It Exists**: Helps catch periods that were never billed
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| contract_id | INTEGER | Contract identifier |
| display_name | TEXT | Client name |
| year | INTEGER | Period year |
| month | INTEGER | Period month (NULL for quarterly) |
| quarter | INTEGER | Period quarter (NULL for monthly) |
| schedule_type | TEXT | Either "monthly" or "quarterly" |
| period_key | INTEGER | Encoded period |
| formatted_period | TEXT | Human-readable period (e.g., "Jan 2025" or "Q4 2024") |

### UI VIEWS

#### v_client_sidebar
Provides data for client selection sidebar.
- **Purpose**: Ready-to-use data for client list component
- **Why It Exists**: Simplifies frontend integration
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| display_name | TEXT | Client name |
| initials | TEXT | First letter of display name |
| provider_name | TEXT | Provider name |
| payment_status | TEXT | "PAID" or "UNPAID" |
| formatted_current_period | TEXT | Human-readable current period |

#### v_client_details
Provides comprehensive client information.
- **Purpose**: Complete data for client details display
- **Why It Exists**: Consolidates data for main client view
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| display_name | TEXT | Client name |
| full_name | TEXT | Legal entity name |
| ima_signed_date | TEXT | Original contract date |
| address | TEXT | Physical address |
| contract_id | INTEGER | Contract identifier |
| contract_number | TEXT | Provider contract ID |
| provider_name | TEXT | Provider name |
| payment_schedule | TEXT | Either "monthly" or "quarterly" |
| fee_type | TEXT | Either "percentage" or "flat" |
| percent_rate | REAL | Percentage rate as decimal |
| flat_rate | REAL | Fixed fee amount |
| participants | INTEGER | Number of participants |
| payment_status | TEXT | "PAID" or "UNPAID" |
| current_period | TEXT | Human-readable current period |
| missing_payment_count | INTEGER | Number of missing payments |
| client_days | REAL | Days since first payment |
| client_since_formatted | TEXT | Formatted date (MM/DD/YYYY) |

#### v_payment_history
Provides complete payment history with document links.
- **Purpose**: Data for payment history table with estimation flags
- **Why It Exists**: Comprehensive payment data with estimates clearly marked
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| payment_id | INTEGER | Payment identifier |
| client_id | INTEGER | Client identifier |
| display_name | TEXT | Client name |
| payment_date_formatted | TEXT | Formatted date (MM/DD/YYYY) |
| period_start_formatted | TEXT | Formatted start period |
| period_end_formatted | TEXT | Formatted end period (if split) |
| aum | INTEGER | Actual AUM (NULL if missing) |
| displayed_aum | INTEGER | AUM for display (actual or estimated) |
| is_estimated_aum | INTEGER | 1 if AUM is estimated |
| expected_fee | REAL | Expected fee from actual data |
| displayed_expected_fee | REAL | Fee for display (actual or estimated) |
| is_estimated_fee | INTEGER | 1 if fee is estimated |
| actual_fee | REAL | Amount received |
| is_split | INTEGER | 1 if split payment |
| variance_amount | REAL | Actual variance amount |
| variance_classification | TEXT | Actual variance classification |
| estimated_variance_amount | REAL | Estimated variance amount |
| estimated_variance_classification | TEXT | Estimated variance classification |
| method | TEXT | Payment method |
| notes | TEXT | Additional information |
| file_id | INTEGER | Document ID |
| file_name | TEXT | Document name |
| onedrive_path | TEXT | Document path |

#### v_last_payment
Shows most recent payment for each client.
- **Purpose**: Quick summary of last payment received
- **Why It Exists**: Used for dashboard and client summary views
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| payment_id | INTEGER | Payment identifier |
| client_id | INTEGER | Client identifier |
| display_name | TEXT | Client name |
| payment_date_formatted | TEXT | Formatted date (MM/DD/YYYY) |
| applied_period | TEXT | Formatted period covered |
| aum | INTEGER | Actual AUM |
| displayed_aum | INTEGER | AUM for display (actual or estimated) |
| is_estimated_aum | INTEGER | 1 if AUM is estimated |
| expected_fee | REAL | Expected fee from actual data |
| displayed_expected_fee | REAL | Fee for display (actual or estimated) |
| is_estimated_fee | INTEGER | 1 if fee is estimated |
| actual_fee | REAL | Amount received |
| variance_amount | REAL | Actual variance amount |
| variance_classification | TEXT | Actual variance classification |
| is_split | INTEGER | 1 if split payment |
| estimated_variance_amount | REAL | Estimated variance amount |
| estimated_variance_classification | TEXT | Estimated variance classification |
| file_id | INTEGER | Document ID |
| file_name | TEXT | Document name |

#### v_missing_payment_periods
Consolidates missing periods for each client.
- **Purpose**: Comma-separated list of missing periods
- **Why It Exists**: Used for client summary display
| Field Name | Data Type | Description |
|------------|-----------|-------------|
| client_id | INTEGER | Client identifier |
| display_name | TEXT | Client name |
| missing_periods | TEXT | Comma-separated list of missed periods |

## END-TO-END INTEGRATION

### WHAT THE DATABASE HANDLES

1. **Period Calculations**:
   - Current billing period determination
   - Period timeline generation
   - Split payment distribution
   - Period formatting for display

2. **Financial Calculations**:
   - Expected fee calculations
   - Variance amount and percentage
   - Variance classification
   - Estimation for missing AUM

3. **Status Tracking**:
   - Payment status (PAID/UNPAID)
   - Missing payment identification
   - Client tenure calculation
   - Document linking

### WHAT THE APPLICATION MUST HANDLE

1. **Authentication & Authorization**:
   - User login
   - Permission management

2. **Period Reference Maintenance**:
   - A scheduled task MUST update the `period_reference` table regularly
   - This should use the following logic:
     - Monthly: Current month is previous month in current year
     - Quarterly: Current quarter is previous quarter (or Q4 of previous year if current is Q1)

3. **File Storage**:
   - Physical file storage in OneDrive
   - File metadata updates in `client_files`
   - Payment-file linking in `payment_files`

4. **Data Entry Validation**:
   - Form validation for payment entry
   - Ensure required fields are populated
   - Handle document uploads

5. **UI State Management**:
   - Client selection state
   - Form edit/create state
   - Document viewer state

6. **UI Enhancement**:
   - Variance coloring and formatting
   - Collapsible split payment rows
   - Document viewer integration
   - Loading states and error handling

### INTEGRATION POINTS

1. **Payment Entry Flow**:
   1. User enters payment data in form
   2. Backend validates and inserts into `payments` table
   3. File upload handled and linked in `payment_files`
   4. Views automatically reflect new payment:
      - `v_payments_expanded` distributes split payments
      - `v_payment_status` updates PAID/UNPAID
      - `v_missing_payments` updates missing periods
      - All UI views reflect new data automatically

2. **Missing Payment Flow**:
   1. `v_missing_payments` identifies missing periods
   2. UI displays missing periods from `v_missing_payment_periods`
   3. User can click to create payment for missing period
   4. Form pre-populates with missing period info

3. **Payment Variance Handling**:
   1. Variances automatically calculated in views
   2. UI displays with color coding (red/green/neutral)
   3. Clear indication when estimates are used

## COMMON GOTCHAS & EDGE CASES

1. **Split Payment Weirdness**:
   - DON'T treat split payments as multiple separate payments
   - DON'T try to allocate split payments based on anything but equal distribution
   - DON'T calculate variance on split payments (intentionally muted)

2. **Missing AUM Data**:
   - Some percentage-based clients have ZERO AUM data (100% missing)
   - Others have sporadic missing values
   - ALWAYS check `is_estimated_aum` and `is_estimated_fee` flags
   - Display estimated values but clearly mark them as such

3. **Date Fields**:
   - Database has inconsistent date formats (some ISO, some not)
   - Use `strftime()` for consistent formatting
   - NEVER trust `ima_signed_date` for client start - use first payment

4. **Current Period Logic**:
   - Billing is IN ARREARS - always one period behind
   - Period reference table MUST be kept current
   - Monthly and quarterly periods move independently

5. **SQLite Type Quirks**:
   - SQLite has flexible typing - be careful with type conversions
   - Use explicit CAST() when type consistency is critical
   - Watch for NULL handling in calculations

## FINAL THOUGHTS

This system is built to minimize application code complexity by leveraging SQLite views. The views handle most of the complex business logic, date math, and fee calculations, so the application code can focus on UI and user experience.

Remember that this is a small internal tool for ~5 users. It doesn't need enterprise-level complexity. Keep it simple, make it work reliably, and focus on the core functionality that replaces their Excel-based workflow.

MOST IMPORTANTLY: Let the database views do their job. They were carefully designed to handle the business logic so you don't have to reimplement it. If you think you need to add complex business logic to the application, first check if a view already handles it!