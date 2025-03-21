-- TABLE DEFINITIONS
-- client_files
CREATE TABLE "client_files" (
    "file_id" INTEGER NOT NULL,
    "client_id" INTEGER NOT NULL,
    "file_name" TEXT NOT NULL,
    "onedrive_path" TEXT NOT NULL,
    "uploaded_at" DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY("file_id" AUTOINCREMENT),
    FOREIGN KEY("client_id") REFERENCES "clients"("client_id") ON DELETE CASCADE
);
-- clients
CREATE TABLE "clients" (
	"client_id"	INTEGER NOT NULL,
	"display_name"	TEXT NOT NULL,
	"full_name"	TEXT,
	"ima_signed_date"	TEXT,
	"onedrive_folder_path"	TEXT,
	"valid_from"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	"valid_to"	DATETIME,
	PRIMARY KEY("client_id" AUTOINCREMENT)
);
-- contacts
CREATE TABLE contacts (
    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    contact_type TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    fax TEXT,
    physical_address TEXT,
    mailing_address TEXT,
    valid_from DATETIME DEFAULT CURRENT_TIMESTAMP,
    valid_to DATETIME,
    FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
);
-- contracts
CREATE TABLE "contracts" (
	"contract_id"	INTEGER NOT NULL,
	"client_id"	INTEGER NOT NULL,
	"contract_number"	TEXT,
	"provider_name"	TEXT,
	"contract_start_date"	TEXT,
	"fee_type"	TEXT,
	"percent_rate"	REAL,
	"flat_rate"	REAL,
	"payment_schedule"	TEXT,
	"num_people"	INTEGER,
	"valid_from"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	"valid_to"	DATETIME, is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
	PRIMARY KEY("contract_id" AUTOINCREMENT),
	FOREIGN KEY("client_id") REFERENCES "clients"("client_id") ON DELETE CASCADE
);
-- payment_files
CREATE TABLE "payment_files" (
    "payment_id" INTEGER NOT NULL,
    "file_id" INTEGER NOT NULL,
    "linked_at" DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY("payment_id", "file_id"),
    FOREIGN KEY("payment_id") REFERENCES "payments"("payment_id") ON DELETE CASCADE,
    FOREIGN KEY("file_id") REFERENCES "client_files"("file_id") ON DELETE CASCADE
);
-- payments
CREATE TABLE "payments" (
	"payment_id"	INTEGER NOT NULL,
	"contract_id"	INTEGER NOT NULL,
	"client_id"	INTEGER NOT NULL,
	"received_date"	TEXT,
	"total_assets"	INTEGER,
	"actual_fee"	REAL,
	"method"	TEXT,
	"notes"	TEXT,
	"valid_from"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	"valid_to"	DATETIME,
	"applied_start_month"	INTEGER,
	"applied_start_month_year"	INTEGER,
	"applied_end_month"	INTEGER,
	"applied_end_month_year"	INTEGER,
	"applied_start_quarter"	INTEGER,
	"applied_start_quarter_year"	INTEGER,
	"applied_end_quarter"	INTEGER,
	"applied_end_quarter_year"	INTEGER,
	PRIMARY KEY("payment_id" AUTOINCREMENT),
	FOREIGN KEY("client_id") REFERENCES "clients"("client_id") ON DELETE CASCADE,
	FOREIGN KEY("contract_id") REFERENCES "contracts"("contract_id") ON DELETE CASCADE
);
-- period_reference
CREATE TABLE period_reference (
    reference_date TEXT PRIMARY KEY,
    current_month_year INTEGER,
    current_month INTEGER,
    current_quarter_year INTEGER,
    current_quarter INTEGER
);
-- VIEW DEFINITIONS
-- distributed_payments
CREATE VIEW distributed_payments AS
WITH payment_analysis AS (
    -- Analyze if payments cover single or multiple periods
    SELECT
        payment_id,
        contract_id,
        client_id,
        received_date,
        actual_fee,
        -- Is this a split payment?
        CASE
            WHEN applied_start_month IS NOT NULL AND applied_end_month IS NOT NULL AND
                 (applied_start_month != applied_end_month OR
                  applied_start_month_year != applied_end_month_year) THEN 1
            WHEN applied_start_quarter IS NOT NULL AND applied_end_quarter IS NOT NULL AND
                 (applied_start_quarter != applied_end_quarter OR
                  applied_start_quarter_year != applied_end_quarter_year) THEN 1
            ELSE 0
        END AS is_split,
        -- What type of period?
        CASE
            WHEN applied_start_month IS NOT NULL THEN 'MONTH'
            WHEN applied_start_quarter IS NOT NULL THEN 'QUARTER'
            ELSE NULL
        END AS period_type,
        -- Store period info directly for non-split payments
        applied_start_month_year,
        applied_start_month,
        applied_start_quarter_year,
        applied_start_quarter,
        -- Calculate absolute period values for split payments
        CASE WHEN applied_start_month IS NOT NULL THEN
            (applied_start_month_year * 12) + applied_start_month
        END AS start_month_abs,
        CASE WHEN applied_end_month IS NOT NULL THEN
            (applied_end_month_year * 12) + applied_end_month
        END AS end_month_abs,
        CASE WHEN applied_start_quarter IS NOT NULL THEN
            (applied_start_quarter_year * 4) + applied_start_quarter
        END AS start_quarter_abs,
        CASE WHEN applied_end_quarter IS NOT NULL THEN
            (applied_end_quarter_year * 4) + applied_end_quarter
        END AS end_quarter_abs
    FROM
        payments
),
-- For single period payments (not split)
single_payments AS (
    SELECT
        payment_id,
        contract_id,
        client_id,
        period_type,
        CASE
            WHEN period_type = 'MONTH' THEN applied_start_month_year
            ELSE applied_start_quarter_year
        END AS period_year,
        CASE
            WHEN period_type = 'MONTH' THEN applied_start_month
            ELSE applied_start_quarter
        END AS period_number,
        is_split,
        actual_fee AS whole_amount,
        actual_fee AS distributed_amount,
        received_date
    FROM
        payment_analysis
    WHERE
        is_split = 0
),
-- For monthly split payments: generate all periods
month_numbers AS (
    WITH RECURSIVE nums(num) AS (
        SELECT 0
        UNION ALL
        SELECT num + 1 FROM nums
        WHERE num < 120
    )
    SELECT num FROM nums
),
-- Generate all monthly periods for split payments
monthly_split AS (
    SELECT
        pa.payment_id,
        pa.contract_id,
        pa.client_id,
        pa.period_type,
        -- Convert back to year/month from absolute month
        (pa.start_month_abs + mn.num) / 12 AS period_year,
        ((pa.start_month_abs + mn.num) % 12) + 1 AS period_number,
        pa.is_split,
        pa.actual_fee AS whole_amount,
        CAST(pa.actual_fee AS REAL) / (pa.end_month_abs - pa.start_month_abs + 1) AS distributed_amount,
        pa.received_date
    FROM
        payment_analysis pa
    JOIN
        month_numbers mn ON
        mn.num >= 0 AND
        mn.num <= (pa.end_month_abs - pa.start_month_abs)
    WHERE
        pa.is_split = 1 AND
        pa.period_type = 'MONTH'
),
-- For quarterly split payments: generate all periods
quarter_numbers AS (
    WITH RECURSIVE nums(num) AS (
        SELECT 0
        UNION ALL
        SELECT num + 1 FROM nums
        WHERE num < 40
    )
    SELECT num FROM nums
),
-- Generate all quarterly periods for split payments
quarterly_split AS (
    SELECT
        pa.payment_id,
        pa.contract_id,
        pa.client_id,
        pa.period_type,
        -- Convert back to year/quarter from absolute quarter
        (pa.start_quarter_abs + qn.num) / 4 AS period_year,
        ((pa.start_quarter_abs + qn.num) % 4) + 1 AS period_number,
        pa.is_split,
        pa.actual_fee AS whole_amount,
        CAST(pa.actual_fee AS REAL) / (pa.end_quarter_abs - pa.start_quarter_abs + 1) AS distributed_amount,
        pa.received_date
    FROM
        payment_analysis pa
    JOIN
        quarter_numbers qn ON
        qn.num >= 0 AND
        qn.num <= (pa.end_quarter_abs - pa.start_quarter_abs)
    WHERE
        pa.is_split = 1 AND
        pa.period_type = 'QUARTER'
)
-- Combine all payments
SELECT * FROM single_payments
UNION ALL
SELECT * FROM monthly_split
UNION ALL
SELECT * FROM quarterly_split
ORDER BY client_id, contract_id, period_type, period_year, period_number;
-- INDEX DEFINITIONS
-- idx_payment_files_payment_id
CREATE INDEX idx_payment_files_payment_id ON payment_files(payment_id);
-- idx_payments_client_date
CREATE INDEX idx_payments_client_date ON payments(client_id, received_date);
-- idx_payments_received_date
CREATE INDEX idx_payments_received_date ON payments(received_date);
-- idx_payments_valid_to
CREATE INDEX idx_payments_valid_to ON payments(valid_to);