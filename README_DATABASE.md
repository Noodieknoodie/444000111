# README_DATABASE.md

//// THE FOLLOWING IS SHORTHAND / MINIFIED / SQL DATABASE SCHEMAS FOR THE DB. THE GOAL WAS TO GIVE ALL THE INFORMATION AS THE ORIGINAL IN LESS TOKENS FOR EFFICIENCY. USE YOUR BRAIN TO FILL IN WHAT THE ACTUAL SQLITE SCHEMA'S BOILERPLATE IS LIKE. 

### TABLES ###

contacts:
- contact_id: INTEGER, PK, AUTOINCREMENT.
- client_id: INTEGER, NOT NULL, FK → clients(client_id) ON DELETE CASCADE.
- contact_type: TEXT, NOT NULL.
- contact_name: TEXT.
- phone: TEXT.
- email: TEXT.
- fax: TEXT.
- physical_address: TEXT.
- mailing_address: TEXT.
- valid_from: DATETIME DEFAULT CURRENT_TIMESTAMP.
- valid_to: DATETIME.

clients:
- client_id: INTEGER, PK, AUTOINCREMENT, NOT NULL.
- display_name: TEXT, NOT NULL.
- full_name: TEXT.
- ima_signed_date: TEXT.
- onedrive_folder_path: TEXT.
- valid_from: DATETIME DEFAULT CURRENT_TIMESTAMP.
- valid_to: DATETIME.

client_files:
- file_id: INTEGER, PK, AUTOINCREMENT, NOT NULL.
- client_id: INTEGER, NOT NULL, FK → clients(client_id) ON DELETE CASCADE.
- file_name: TEXT, NOT NULL.
- onedrive_path: TEXT, NOT NULL.
- uploaded_at: DATETIME DEFAULT CURRENT_TIMESTAMP.

payment_files:
- payment_id: INTEGER, NOT NULL, FK → payments(payment_id) ON DELETE CASCADE.
- file_id: INTEGER, NOT NULL, FK → client_files(file_id) ON DELETE CASCADE.
- linked_at: DATETIME DEFAULT CURRENT_TIMESTAMP.
- Composite PK: (payment_id, file_id).

contracts:
- contract_id: INTEGER, PK, AUTOINCREMENT, NOT NULL.
- client_id: INTEGER, NOT NULL, FK → clients(client_id) ON DELETE CASCADE.
- contract_number: TEXT.
- provider_name: TEXT.
- contract_start_date: TEXT.
- fee_type: TEXT.
- percent_rate: REAL.
- flat_rate: REAL.
- payment_schedule: TEXT.
- num_people: INTEGER.
- valid_from: DATETIME DEFAULT CURRENT_TIMESTAMP.
- valid_to: DATETIME.
- is_active: INTEGER NOT NULL DEFAULT 1, CHECK (is_active IN (0,1)).

payments:
- payment_id: INTEGER, PK, AUTOINCREMENT, NOT NULL.
- contract_id: INTEGER, NOT NULL, FK → contracts(contract_id) ON DELETE CASCADE.
- client_id: INTEGER, NOT NULL, FK → clients(client_id) ON DELETE CASCADE.
- received_date: TEXT.
- total_assets: INTEGER.
- actual_fee: REAL.
- method: TEXT.
- notes: TEXT.
- valid_from: DATETIME DEFAULT CURRENT_TIMESTAMP.
- valid_to: DATETIME.
- applied_start_month: INTEGER.
- applied_start_month_year: INTEGER.
- applied_end_month: INTEGER.
- applied_end_month_year: INTEGER.
- applied_start_quarter: INTEGER.
- applied_start_quarter_year: INTEGER.
- applied_end_quarter: INTEGER.
- applied_end_quarter_year: INTEGER.

period_reference:
- reference_date: TEXT, PK.
- current_month_year: INTEGER.
- current_month: INTEGER.
- current_quarter_year: INTEGER.
- current_quarter: INTEGER.


### INDEX ###

idx_payments_received_date ON payments(received_date)');
idx_payments_client_date ON payments(client_id, received_date)');
idx_payment_files_payment_id ON payment_files(payment_id)');
idx_payments_valid_to ON payments(valid_to)');



### VIEWS ###

v_active_contracts:
- FROM: contracts (c)
- WHERE: c.valid_to IS NULL AND c.is_active = 1
- SELECT: all columns (c.*)

v_all_periods:
- UNION ALL of two queries:
  - Monthly: FROM v_monthly_periods; fields: client_id, contract_id, year, month, quarter=NULL, schedule_type='monthly', period_key
  - Quarterly: FROM v_quarterly_periods; fields: client_id, contract_id, year, month=NULL, quarter, schedule_type='quarterly', period_key

v_client_aum_history:
- WITH ranked_aum: selects from v_payments_expanded (p) where total_assets IS NOT NULL, ranking rows per client by period_key DESC
- Main SELECT: FROM v_all_periods (a) LEFT JOIN v_payments_expanded (p) on client_id and period_key
- Fields: client_id, contract_id, year, month, quarter, schedule_type, period_key, actual_aum (p.total_assets)
- estimated_aum: if p.total_assets IS NULL, then lookup from ranked_aum; else use p.total_assets
- is_estimated_aum flag: 1 if total_assets missing and ranked_aum exists, else 0

v_client_details:
- FROM: clients (c)
  JOIN v_active_contracts (con) ON c.client_id = con.client_id
  JOIN v_payment_status (ps) ON c.client_id = ps.client_id
  JOIN v_client_first_payment (fp) ON c.client_id = fp.client_id
- SELECT: client_id, display_name, full_name, ima_signed_date,
  address (subquery from contacts with contact_type 'Primary' and valid_to IS NULL),
  contract details (con.contract_id, contract_number, provider_name, payment_schedule, fee_type, percent_rate, flat_rate, participants),
  payment_status, current_period, missing_payment_count (subquery from v_missing_payments), client_days, client_since_formatted
- WHERE: c.valid_to IS NULL

v_client_first_payment:
- FROM: clients (c) LEFT JOIN payments (p) ON c.client_id = p.client_id AND p.valid_to IS NULL
- GROUP BY: c.client_id, c.display_name
- SELECT: client_id, display_name,
  first_payment_date = MIN(p.received_date),
  client_days = julianday('now') - julianday(MIN(p.received_date)),
  client_since_formatted = formatted MIN(p.received_date) (MM/DD/YYYY)
- WHERE: c.valid_to IS NULL

v_client_sidebar:
- FROM: clients (c)
  JOIN v_active_contracts (con) ON c.client_id = con.client_id
  JOIN v_payment_status (ps) ON c.client_id = ps.client_id
- SELECT: client_id, display_name, initials (first letter of display_name),
  provider_name (from con), payment_status and formatted_current_period (from ps)
- WHERE: c.valid_to IS NULL
- ORDER BY: c.display_name


v_current_period:
- FROM period_reference.
- SELECT reference_date, current_month_year AS monthly_year, current_month AS monthly_month, current_quarter_year AS quarterly_year, current_quarter AS quarterly_quarter.
- ORDER BY reference_date DESC; LIMIT 1.

v_expected_fees:
- FROM v_all_periods (a) LEFT JOIN v_payments_expanded (p) ON a.client_id = p.client_id AND a.period_key = p.period_key; JOIN v_active_contracts (c) ON a.contract_id = c.contract_id.
- SELECT a.client_id, a.contract_id, year, month, quarter, schedule_type, period_key, fee_type, percent_rate, flat_rate, assets_under_management = p.total_assets.
- Compute expected_fee: if fee_type = 'percentage' and total_assets exists then ROUND(total_assets * percent_rate,2); if fee_type = 'flat' then flat_rate; else NULL.
- Also select p.payment_id, actual_fee = p.period_fee, and p.is_split.

v_expected_fees_with_estimates:
- FROM v_expected_fees (ef) LEFT JOIN v_client_aum_history (aum) ON ef.client_id = aum.client_id AND ef.period_key = aum.period_key.
- SELECT all ef columns, plus aum.estimated_aum, aum.is_estimated_aum.
- Compute estimated_expected_fee: if fee_type = 'percentage' and expected_fee is NULL and estimated_aum exists then ROUND(estimated_aum * percent_rate,2); if fee_type = 'flat' and expected_fee is NULL then flat_rate; else expected_fee.
- Compute is_estimated_fee: 1 if expected_fee is NULL and (fee_type conditions met) else 0.

v_last_payment:
- WITH ranked_payments: SELECT all columns from v_payment_history (ph) plus ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY payment_date_formatted DESC) AS row_num.
- SELECT from ranked_payments (rp) where row_num = 1.
- Return payment_id, client_id, display_name, payment_date_formatted, applied_period = period_start_formatted || period_end_formatted, aum, displayed_aum, is_estimated_aum, expected_fee, displayed_expected_fee, is_estimated_fee, actual_fee, variance_amount, variance_classification, is_split, estimated_variance_amount, estimated_variance_classification, file_id, file_name.

v_missing_payment_periods:
- FROM v_missing_payments.
- GROUP BY client_id, display_name.
- SELECT client_id, display_name, and GROUP_CONCAT(formatted_period, ', ') AS missing_periods.

v_missing_payments:
- FROM v_payment_variance (v) JOIN clients (c) ON v.client_id = c.client_id.
- WHERE v.payment_id IS NULL AND c.valid_to IS NULL.
- SELECT client_id, contract_id, c.display_name, year, month, quarter, schedule_type, period_key.
- Compute formatted_period: if schedule_type = 'monthly' then map month (1–12 to Jan–Dec) concatenated with year; if 'quarterly' then 'Q' + quarter + year.
- ORDER BY v.client_id, v.period_key.

v_monthly_periods:
- WITH client_periods: SELECT c.client_id, c.contract_id, MIN(CASE WHEN p.applied_start_month IS NOT NULL THEN (p.applied_start_month_year * 100 + p.applied_start_month) END) AS first_period, and current_period from v_current_period as (monthly_year * 100 + monthly_month) from v_active_contracts (c) LEFT JOIN payments (p) ON c.client_id = p.client_id AND p.valid_to IS NULL; filter WHERE payment_schedule = 'monthly'; GROUP BY client_id, contract_id.
- WITH RECURSIVE months(period): start at MIN(first_period) from client_periods; increment month by month (rollover December to January with year increment) until reaching MAX(current_period).
- SELECT cp.client_id, cp.contract_id, year = period/100, month = period % 100, period AS period_key from client_periods (cp) JOIN months (m) where m.period BETWEEN cp.first_period AND cp.current_period.


v_payment_history:
- FROM: payments (p) JOIN clients (c) JOIN v_active_contracts (con) LEFT JOIN payment_files (pf) LEFT JOIN client_files (cf)
- SELECT: p.payment_id, p.client_id, c.display_name, formatted payment_date (MM/DD/YYYY)
  - period_start_formatted: if p.applied_start_month exists → map month number to abbreviation + p.applied_start_month_year; else "Q" + p.applied_start_quarter + ' ' + p.applied_start_quarter_year
  - period_end_formatted: if start ≠ end → " to " + mapped end (month or quarter), else blank
  - aum: p.total_assets; displayed_aum: if fee type 'percentage' and aum missing then lookup estimated AUM from v_client_aum_history; flag is_estimated_aum accordingly
  - expected_fee: if fee type 'percentage' with aum then ROUND(aum * con.percent_rate,2); if 'flat' then con.flat_rate; else NULL
  - displayed_expected_fee: for missing aum in percentage fee, lookup from v_expected_fees_with_estimates; else same as expected_fee; flag is_estimated_fee if lookup used
  - p.actual_fee; is_split flag if period differs; variance_amount: if not split then actual_fee minus expected fee; variance_classification: if not split then classify based on diff (within 3 → "Within Target", > expected → "Overpaid", < expected → "Underpaid")
  - estimated_variance_amount/classification: for fee type 'percentage' with missing aum, lookup from v_payment_variance_with_estimates
  - Also include p.method, p.notes and file info (cf.file_id, cf.file_name, cf.onedrive_path)
- WHERE: p.valid_to IS NULL and c.valid_to IS NULL; ORDER BY p.client_id, p.received_date DESC

v_payment_status:
- WITH current_period: SELECT from v_current_period
- WITH current_payment_status: FROM clients (c) JOIN v_active_contracts (con)
  - Compute current_year, current_month (if monthly) or current_quarter (if quarterly) and current_period_key from current_period
  - Set payment_status to 'PAID' if a matching record exists in v_payments_expanded for current_period_key; else 'UNPAID'
- SELECT: All fields from current_payment_status plus formatted_current_period, which maps current_month to its abbreviation (if monthly) or uses "Q" + current_quarter for quarterly

v_payment_variance:
- FROM v_expected_fees (ef)
- Compute variance_amount: if is_split, or actual_fee or expected_fee is NULL then NULL; else ROUND(actual_fee - expected_fee, 2)
- Compute variance_percentage: if valid (non-null and expected_fee ≠ 0) then ROUND((actual_fee - expected_fee) / expected_fee * 100, 2); else NULL
- Compute variance_classification: if not split then if |diff| ≤ 3 → "Within Target", if actual_fee > expected_fee → "Overpaid", else "Underpaid"; else NULL

v_payment_variance_with_estimates:
- FROM v_expected_fees_with_estimates (ef)
- Compute variance_amount, variance_percentage, and variance_classification similar to v_payment_variance but using estimated_expected_fee in place of expected_fee
- Include ef.is_estimated_fee

v_payments_expanded:
- WITH monthly_payments:
  - FROM payments (p) JOIN v_active_contracts (c) WHERE p.valid_to IS NULL, p.applied_start_month is present, and c.payment_schedule = 'monthly'
  - Calculate: periods_covered (via count from v_monthly_periods between start and end), start_period_key (applied_start_month_year * 100 + applied_start_month), end_period_key (applied_end_month_year * 100 + applied_end_month), schedule_type = 'monthly', and is_split flag (if start and end differ)
- WITH quarterly_payments:
  - Similar to monthly_payments but for quarterly fields (using applied_start_quarter) and c.payment_schedule = 'quarterly'
- UNION ALL:
  - For monthly: JOIN v_monthly_periods (mp) on client_id and filter where mp.period_key BETWEEN start_period_key and end_period_key; SELECT payment_id, client_id, contract_id, received_date, total_assets, period_fee (if is_split then actual_fee/periods_covered else actual_fee), total_fee = actual_fee, mp.year, mp.month, NULL as quarter, schedule_type, mp.period_key, is_split, start_period_key, end_period_key, periods_covered
  - For quarterly: JOIN v_quarterly_periods (qp) similarly (month = NULL, quarter provided)

v_quarterly_periods:
- WITH client_periods:
  - FROM v_active_contracts (c) LEFT JOIN payments (p) WHERE c.payment_schedule = 'quarterly'
  - Calculate first_period as MIN(applied_start_quarter_year * 10 + applied_start_quarter) and current_period from v_current_period (quarterly_year * 10 + quarterly_quarter)
  - GROUP BY client_id, contract_id
- WITH RECURSIVE quarters:
  - Generate periods starting from MIN(first_period), incrementing: if period mod 10 = 4 then next = (period/10 + 1) * 10 + 1, else period + 1, until period reaches MAX(current_period)
- SELECT: client_id, contract_id, year = period/10, quarter = period % 10, period AS period_key
- WHERE: period between first_period and current_period
