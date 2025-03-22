# README_DEV_BIBLE_1.md

# HOHIMERPRO - THE 401(k) PAYMENT MANAGEMENT SYSTEM - DEVELOPER'S BIBLE

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

**(SEE README_DATABASE.md)**

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
// NONE - this is a small internal tool for ~5 users

2. **Period Reference Maintenance**:
   - A scheduled task MUST update the `period_reference` table (see README_LLM.md)
   - This should use the following logic:
     - Monthly: Current month is previous month in current year
     - Quarterly: Current quarter is previous quarter (or Q4 of previous year if current is Q1)

3. **File Storage**: (see README_FILE_SYSTEM.md)
   - Primary document storage in central mail dump folder
   - Windows shortcuts in client folders pointing to original files
   - Document metadata stored in `client_files` table
   - Many-to-many relationships managed in `payment_files` table

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
   3. Document handling:
      - Document uploaded to mail dump folder
      - Metadata stored in `client_files` table
      - Association created in `payment_files` table
      - Windows shortcuts generated in client folders
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