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
-- v_active_contracts
CREATE VIEW v_active_contracts AS
SELECT
    c.*
FROM contracts c
WHERE c.valid_to IS NULL
AND c.is_active = 1;
-- v_all_periods
CREATE VIEW v_all_periods AS
-- Monthly periods
SELECT
    client_id,
    contract_id,
    year,
    month,
    NULL AS quarter,
    'monthly' AS schedule_type,
    period_key
FROM v_monthly_periods
UNION ALL
-- Quarterly periods
SELECT
    client_id,
    contract_id,
    year,
    NULL AS month,
    quarter,
    'quarterly' AS schedule_type,
    period_key
FROM v_quarterly_periods;
-- v_client_aum_history
CREATE VIEW v_client_aum_history AS
WITH ranked_aum AS (
    SELECT
        p.client_id,
        p.contract_id,
        p.period_key,
        p.total_assets,
        p.schedule_type,
        ROW_NUMBER() OVER (PARTITION BY p.client_id ORDER BY p.period_key DESC) AS aum_recency_rank
    FROM v_payments_expanded p
    WHERE p.total_assets IS NOT NULL
)
SELECT
    a.client_id,
    a.contract_id,
    a.year,
    a.month,
    a.quarter,
    a.schedule_type,
    a.period_key,
    p.total_assets AS actual_aum,
    CASE
        WHEN p.total_assets IS NULL THEN
            (SELECT ra.total_assets FROM ranked_aum ra
             WHERE ra.client_id = a.client_id
             ORDER BY ra.aum_recency_rank
             LIMIT 1)
        ELSE p.total_assets
    END AS estimated_aum,
    CASE
        WHEN p.total_assets IS NULL AND EXISTS (
            SELECT 1 FROM ranked_aum ra WHERE ra.client_id = a.client_id
        ) THEN 1
        ELSE 0
    END AS is_estimated_aum
FROM v_all_periods a
LEFT JOIN v_payments_expanded p ON a.client_id = p.client_id AND a.period_key = p.period_key;
-- v_client_details
CREATE VIEW v_client_details AS
SELECT
    c.client_id,
    c.display_name,
    c.full_name,
    c.ima_signed_date,
    (SELECT physical_address FROM contacts WHERE client_id = c.client_id AND contact_type = 'Primary' AND valid_to IS NULL LIMIT 1) AS address,
    con.contract_id,
    con.contract_number,
    con.provider_name,
    con.payment_schedule,
    con.fee_type,
    con.percent_rate,
    con.flat_rate,
    con.num_people AS participants,
    ps.payment_status,
    ps.formatted_current_period AS current_period,
    (
        SELECT COUNT(*)
        FROM v_missing_payments mp
        WHERE mp.client_id = c.client_id
    ) AS missing_payment_count,
    fp.client_days,
    fp.client_since_formatted
FROM clients c
JOIN v_active_contracts con ON c.client_id = con.client_id
JOIN v_payment_status ps ON c.client_id = ps.client_id
JOIN v_client_first_payment fp ON c.client_id = fp.client_id
WHERE c.valid_to IS NULL;
-- v_client_first_payment
CREATE VIEW v_client_first_payment AS
SELECT
    c.client_id,
    c.display_name,
    MIN(p.received_date) AS first_payment_date,
    julianday('now') - julianday(MIN(p.received_date)) AS client_days,
    strftime('%m/%d/%Y', MIN(p.received_date)) AS client_since_formatted
FROM clients c
LEFT JOIN payments p ON c.client_id = p.client_id AND p.valid_to IS NULL
WHERE c.valid_to IS NULL
GROUP BY c.client_id, c.display_name;
-- v_client_sidebar
CREATE VIEW v_client_sidebar AS
SELECT
    c.client_id,
    c.display_name,
    SUBSTR(c.display_name, 1, 1) AS initials,
    con.provider_name,
    ps.payment_status,
    ps.formatted_current_period
FROM clients c
JOIN v_active_contracts con ON c.client_id = con.client_id
JOIN v_payment_status ps ON c.client_id = ps.client_id
WHERE c.valid_to IS NULL
ORDER BY c.display_name;
-- v_current_period
CREATE VIEW v_current_period AS
SELECT
    reference_date,
    current_month_year AS monthly_year,
    current_month AS monthly_month,
    current_quarter_year AS quarterly_year,
    current_quarter AS quarterly_quarter
FROM period_reference
ORDER BY reference_date DESC
LIMIT 1;
-- v_expected_fees
CREATE VIEW v_expected_fees AS
SELECT
    a.client_id,
    a.contract_id,
    a.year,
    a.month,
    a.quarter,
    a.schedule_type,
    a.period_key,
    c.fee_type,
    c.percent_rate,
    c.flat_rate,
    p.total_assets AS assets_under_management,
    CASE
        WHEN c.fee_type = 'percentage' AND p.total_assets IS NOT NULL THEN ROUND(p.total_assets * c.percent_rate, 2)
        WHEN c.fee_type = 'flat' THEN c.flat_rate
        ELSE NULL
    END AS expected_fee,
    p.payment_id,
    p.period_fee AS actual_fee,
    p.is_split
FROM v_all_periods a
LEFT JOIN v_payments_expanded p ON a.client_id = p.client_id AND a.period_key = p.period_key
JOIN v_active_contracts c ON a.contract_id = c.contract_id;
-- v_expected_fees_with_estimates
CREATE VIEW v_expected_fees_with_estimates AS
SELECT
    ef.*,
    aum.estimated_aum,
    aum.is_estimated_aum,
    CASE
        WHEN ef.fee_type = 'percentage' AND ef.expected_fee IS NULL AND aum.estimated_aum IS NOT NULL
        THEN ROUND(aum.estimated_aum * ef.percent_rate, 2)
        WHEN ef.fee_type = 'flat' AND ef.expected_fee IS NULL
        THEN ef.flat_rate
        ELSE ef.expected_fee
    END AS estimated_expected_fee,
    CASE
        WHEN ef.expected_fee IS NULL AND
             (ef.fee_type = 'percentage' AND aum.estimated_aum IS NOT NULL OR ef.fee_type = 'flat')
        THEN 1
        ELSE 0
    END AS is_estimated_fee
FROM v_expected_fees ef
LEFT JOIN v_client_aum_history aum ON ef.client_id = aum.client_id AND ef.period_key = aum.period_key;
-- v_last_payment
CREATE VIEW v_last_payment AS
WITH
ranked_payments AS (
    SELECT
        ph.*,
        ROW_NUMBER() OVER (PARTITION BY ph.client_id ORDER BY ph.payment_date_formatted DESC) AS row_num
    FROM v_payment_history ph
)
SELECT
    rp.payment_id,
    rp.client_id,
    rp.display_name,
    rp.payment_date_formatted,
    rp.period_start_formatted || rp.period_end_formatted AS applied_period,
    rp.aum,
    rp.displayed_aum,
    rp.is_estimated_aum,
    rp.expected_fee,
    rp.displayed_expected_fee,
    rp.is_estimated_fee,
    rp.actual_fee,
    rp.variance_amount,
    rp.variance_classification,
    rp.is_split,
    rp.estimated_variance_amount,
    rp.estimated_variance_classification,
    rp.file_id,
    rp.file_name
FROM ranked_payments rp
WHERE rp.row_num = 1;
-- v_missing_payment_periods
CREATE VIEW v_missing_payment_periods AS
SELECT
    client_id,
    display_name,
    GROUP_CONCAT(formatted_period, ', ') AS missing_periods
FROM v_missing_payments
GROUP BY client_id, display_name;
-- v_missing_payments
CREATE VIEW v_missing_payments AS
SELECT
    v.client_id,
    v.contract_id,
    c.display_name,
    v.year,
    v.month,
    v.quarter,
    v.schedule_type,
    v.period_key,
    CASE
        WHEN v.schedule_type = 'monthly' THEN
            CASE
                WHEN v.month = 1 THEN 'Jan'
                WHEN v.month = 2 THEN 'Feb'
                WHEN v.month = 3 THEN 'Mar'
                WHEN v.month = 4 THEN 'Apr'
                WHEN v.month = 5 THEN 'May'
                WHEN v.month = 6 THEN 'Jun'
                WHEN v.month = 7 THEN 'Jul'
                WHEN v.month = 8 THEN 'Aug'
                WHEN v.month = 9 THEN 'Sep'
                WHEN v.month = 10 THEN 'Oct'
                WHEN v.month = 11 THEN 'Nov'
                WHEN v.month = 12 THEN 'Dec'
            END || ' ' || v.year
        WHEN v.schedule_type = 'quarterly' THEN
            'Q' || v.quarter || ' ' || v.year
    END AS formatted_period
FROM v_payment_variance v
JOIN clients c ON v.client_id = c.client_id
WHERE v.payment_id IS NULL
AND c.valid_to IS NULL
ORDER BY v.client_id, v.period_key;
-- v_monthly_periods
CREATE VIEW v_monthly_periods AS
WITH
client_periods AS (
    SELECT
        c.client_id,
        c.contract_id,
        MIN(CASE WHEN p.applied_start_month IS NOT NULL
            THEN p.applied_start_month_year * 100 + p.applied_start_month
            ELSE NULL END) AS first_period,
        (SELECT cp.monthly_year * 100 + cp.monthly_month FROM v_current_period cp) AS current_period
    FROM v_active_contracts c
    LEFT JOIN payments p ON c.client_id = p.client_id AND p.valid_to IS NULL
    WHERE c.payment_schedule = 'monthly'
    GROUP BY c.client_id, c.contract_id
)
SELECT
    cp.client_id,
    cp.contract_id,
    period / 100 AS year,
    period % 100 AS month,
    period AS period_key
FROM client_periods cp
JOIN (
    WITH RECURSIVE months(period) AS (
        SELECT MIN(first_period) FROM client_periods
        UNION ALL
        SELECT
            CASE
                WHEN period % 100 = 12 THEN (period / 100 + 1) * 100 + 1
                ELSE period + 1
            END
        FROM months
        WHERE period < (SELECT MAX(current_period) FROM client_periods)
    )
    SELECT period FROM months
) m
WHERE m.period >= cp.first_period
AND m.period <= cp.current_period;
-- v_payment_history
CREATE VIEW v_payment_history AS
SELECT
    p.payment_id,
    p.client_id,
    c.display_name,
    strftime('%m/%d/%Y', p.received_date) AS payment_date_formatted,
    CASE
        WHEN p.applied_start_month IS NOT NULL THEN
            CASE
                WHEN p.applied_start_month = 1 THEN 'Jan'
                WHEN p.applied_start_month = 2 THEN 'Feb'
                WHEN p.applied_start_month = 3 THEN 'Mar'
                WHEN p.applied_start_month = 4 THEN 'Apr'
                WHEN p.applied_start_month = 5 THEN 'May'
                WHEN p.applied_start_month = 6 THEN 'Jun'
                WHEN p.applied_start_month = 7 THEN 'Jul'
                WHEN p.applied_start_month = 8 THEN 'Aug'
                WHEN p.applied_start_month = 9 THEN 'Sep'
                WHEN p.applied_start_month = 10 THEN 'Oct'
                WHEN p.applied_start_month = 11 THEN 'Nov'
                WHEN p.applied_start_month = 12 THEN 'Dec'
            END || ' ' || p.applied_start_month_year
        ELSE
            'Q' || p.applied_start_quarter || ' ' || p.applied_start_quarter_year
    END AS period_start_formatted,
    CASE
        WHEN (p.applied_start_month IS NOT NULL AND
             (p.applied_start_month != p.applied_end_month OR
              p.applied_start_month_year != p.applied_end_month_year)) OR
             (p.applied_start_quarter IS NOT NULL AND
             (p.applied_start_quarter != p.applied_end_quarter OR
              p.applied_start_quarter_year != p.applied_end_quarter_year))
        THEN
            CASE
                WHEN p.applied_end_month IS NOT NULL THEN
                    ' to ' ||
                    CASE
                        WHEN p.applied_end_month = 1 THEN 'Jan'
                        WHEN p.applied_end_month = 2 THEN 'Feb'
                        WHEN p.applied_end_month = 3 THEN 'Mar'
                        WHEN p.applied_end_month = 4 THEN 'Apr'
                        WHEN p.applied_end_month = 5 THEN 'May'
                        WHEN p.applied_end_month = 6 THEN 'Jun'
                        WHEN p.applied_end_month = 7 THEN 'Jul'
                        WHEN p.applied_end_month = 8 THEN 'Aug'
                        WHEN p.applied_end_month = 9 THEN 'Sep'
                        WHEN p.applied_end_month = 10 THEN 'Oct'
                        WHEN p.applied_end_month = 11 THEN 'Nov'
                        WHEN p.applied_end_month = 12 THEN 'Dec'
                    END || ' ' || p.applied_end_month_year
                ELSE
                    ' to Q' || p.applied_end_quarter || ' ' || p.applied_end_quarter_year
            END
        ELSE ''
    END AS period_end_formatted,
    p.total_assets AS aum,
    CASE
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NULL
        THEN (SELECT estimated_aum FROM v_client_aum_history WHERE client_id = p.client_id
              AND ((p.applied_start_month IS NOT NULL AND period_key = p.applied_start_month_year * 100 + p.applied_start_month)
                   OR (p.applied_start_quarter IS NOT NULL AND period_key = p.applied_start_quarter_year * 10 + p.applied_start_quarter))
              LIMIT 1)
        ELSE p.total_assets
    END AS displayed_aum,
    CASE
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NULL AND
             EXISTS (SELECT 1 FROM v_client_aum_history WHERE client_id = p.client_id AND estimated_aum IS NOT NULL LIMIT 1)
        THEN 1
        ELSE 0
    END AS is_estimated_aum,
    CASE
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NOT NULL
        THEN ROUND(p.total_assets * con.percent_rate, 2)
        WHEN con.fee_type = 'flat'
        THEN con.flat_rate
        ELSE NULL
    END AS expected_fee,
    CASE
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NULL
        THEN (SELECT estimated_expected_fee FROM v_expected_fees_with_estimates WHERE client_id = p.client_id
              AND ((p.applied_start_month IS NOT NULL AND period_key = p.applied_start_month_year * 100 + p.applied_start_month)
                   OR (p.applied_start_quarter IS NOT NULL AND period_key = p.applied_start_quarter_year * 10 + p.applied_start_quarter))
              LIMIT 1)
        WHEN con.fee_type = 'flat'
        THEN con.flat_rate
        ELSE CASE
                WHEN con.fee_type = 'percentage' AND p.total_assets IS NOT NULL
                THEN ROUND(p.total_assets * con.percent_rate, 2)
                ELSE NULL
             END
    END AS displayed_expected_fee,
    CASE
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NULL AND
             EXISTS (SELECT 1 FROM v_expected_fees_with_estimates WHERE client_id = p.client_id AND is_estimated_fee = 1 LIMIT 1)
        THEN 1
        ELSE 0
    END AS is_estimated_fee,
    p.actual_fee,
    CASE
        WHEN (p.applied_start_month IS NOT NULL AND
             (p.applied_start_month != p.applied_end_month OR
              p.applied_start_month_year != p.applied_end_month_year)) OR
             (p.applied_start_quarter IS NOT NULL AND
             (p.applied_start_quarter != p.applied_end_quarter OR
              p.applied_start_quarter_year != p.applied_end_quarter_year))
        THEN 1
        ELSE 0
    END AS is_split,
    CASE
        WHEN (p.applied_start_month IS NOT NULL AND
             (p.applied_start_month != p.applied_end_month OR
              p.applied_start_month_year != p.applied_end_month_year)) OR
             (p.applied_start_quarter IS NOT NULL AND
             (p.applied_start_quarter != p.applied_end_quarter OR
              p.applied_start_quarter_year != p.applied_end_quarter_year))
        THEN NULL -- Mute variance for split payments
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NOT NULL
        THEN ROUND(p.actual_fee - (p.total_assets * con.percent_rate), 2)
        WHEN con.fee_type = 'flat'
        THEN ROUND(p.actual_fee - con.flat_rate, 2)
        ELSE NULL
    END AS variance_amount,
    CASE
        WHEN (p.applied_start_month IS NOT NULL AND
             (p.applied_start_month != p.applied_end_month OR
              p.applied_start_month_year != p.applied_end_month_year)) OR
             (p.applied_start_quarter IS NOT NULL AND
             (p.applied_start_quarter != p.applied_end_quarter OR
              p.applied_start_quarter_year != p.applied_end_quarter_year))
        THEN NULL -- Mute classification for split payments
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NOT NULL
        THEN
            CASE
                WHEN ABS(p.actual_fee - (p.total_assets * con.percent_rate)) <= 3 THEN 'Within Target'
                WHEN p.actual_fee > (p.total_assets * con.percent_rate) THEN 'Overpaid'
                ELSE 'Underpaid'
            END
        WHEN con.fee_type = 'flat'
        THEN
            CASE
                WHEN ABS(p.actual_fee - con.flat_rate) <= 3 THEN 'Within Target'
                WHEN p.actual_fee > con.flat_rate THEN 'Overpaid'
                ELSE 'Underpaid'
            END
        ELSE NULL
    END AS variance_classification,
    CASE
        WHEN (p.applied_start_month IS NOT NULL AND
             (p.applied_start_month != p.applied_end_month OR
              p.applied_start_month_year != p.applied_end_month_year)) OR
             (p.applied_start_quarter IS NOT NULL AND
             (p.applied_start_quarter != p.applied_end_quarter OR
              p.applied_start_quarter_year != p.applied_end_quarter_year))
        THEN NULL -- Mute variance for split payments
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NULL AND
             EXISTS (SELECT 1 FROM v_payment_variance_with_estimates WHERE client_id = p.client_id AND variance_amount IS NOT NULL LIMIT 1)
        THEN (SELECT variance_amount FROM v_payment_variance_with_estimates WHERE client_id = p.client_id
              AND ((p.applied_start_month IS NOT NULL AND period_key = p.applied_start_month_year * 100 + p.applied_start_month)
                   OR (p.applied_start_quarter IS NOT NULL AND period_key = p.applied_start_quarter_year * 10 + p.applied_start_quarter))
              LIMIT 1)
        ELSE NULL
    END AS estimated_variance_amount,
    CASE
        WHEN (p.applied_start_month IS NOT NULL AND
             (p.applied_start_month != p.applied_end_month OR
              p.applied_start_month_year != p.applied_end_month_year)) OR
             (p.applied_start_quarter IS NOT NULL AND
             (p.applied_start_quarter != p.applied_end_quarter OR
              p.applied_start_quarter_year != p.applied_end_quarter_year))
        THEN NULL -- Mute classification for split payments
        WHEN con.fee_type = 'percentage' AND p.total_assets IS NULL AND
             EXISTS (SELECT 1 FROM v_payment_variance_with_estimates WHERE client_id = p.client_id AND variance_classification IS NOT NULL LIMIT 1)
        THEN (SELECT variance_classification FROM v_payment_variance_with_estimates WHERE client_id = p.client_id
              AND ((p.applied_start_month IS NOT NULL AND period_key = p.applied_start_month_year * 100 + p.applied_start_month)
                   OR (p.applied_start_quarter IS NOT NULL AND period_key = p.applied_start_quarter_year * 10 + p.applied_start_quarter))
              LIMIT 1)
        ELSE NULL
    END AS estimated_variance_classification,
    p.method,
    p.notes,
    cf.file_id,
    cf.file_name,
    cf.onedrive_path
FROM payments p
JOIN clients c ON p.client_id = c.client_id
JOIN v_active_contracts con ON p.contract_id = con.contract_id
LEFT JOIN payment_files pf ON p.payment_id = pf.payment_id
LEFT JOIN client_files cf ON pf.file_id = cf.file_id
WHERE p.valid_to IS NULL
AND c.valid_to IS NULL
ORDER BY p.client_id, p.received_date DESC;
-- v_payment_status
CREATE VIEW v_payment_status AS
WITH
current_period AS (
    SELECT * FROM v_current_period
),
current_payment_status AS (
    SELECT
        c.client_id,
        con.contract_id,
        c.display_name,
        con.payment_schedule,
        CASE
            WHEN con.payment_schedule = 'monthly' THEN
                (SELECT cp.monthly_year FROM current_period cp)
            ELSE
                (SELECT cp.quarterly_year FROM current_period cp)
        END AS current_year,
        CASE
            WHEN con.payment_schedule = 'monthly' THEN
                (SELECT cp.monthly_month FROM current_period cp)
            ELSE
                NULL
        END AS current_month,
        CASE
            WHEN con.payment_schedule = 'quarterly' THEN
                (SELECT cp.quarterly_quarter FROM current_period cp)
            ELSE
                NULL
        END AS current_quarter,
        CASE
            WHEN con.payment_schedule = 'monthly' THEN
                (SELECT cp.monthly_year * 100 + cp.monthly_month FROM current_period cp)
            ELSE
                (SELECT cp.quarterly_year * 10 + cp.quarterly_quarter FROM current_period cp)
        END AS current_period_key,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM v_payments_expanded p
                WHERE p.client_id = c.client_id
                AND (
                    (con.payment_schedule = 'monthly' AND p.period_key = (SELECT cp.monthly_year * 100 + cp.monthly_month FROM current_period cp)) OR
                    (con.payment_schedule = 'quarterly' AND p.period_key = (SELECT cp.quarterly_year * 10 + cp.quarterly_quarter FROM current_period cp))
                )
            ) THEN 'PAID'
            ELSE 'UNPAID'
        END AS payment_status
    FROM clients c
    JOIN v_active_contracts con ON c.client_id = con.client_id
    WHERE c.valid_to IS NULL
)
SELECT
    cps.*,
    CASE
        WHEN cps.payment_schedule = 'monthly' THEN
            CASE
                WHEN cps.current_month = 1 THEN 'Jan'
                WHEN cps.current_month = 2 THEN 'Feb'
                WHEN cps.current_month = 3 THEN 'Mar'
                WHEN cps.current_month = 4 THEN 'Apr'
                WHEN cps.current_month = 5 THEN 'May'
                WHEN cps.current_month = 6 THEN 'Jun'
                WHEN cps.current_month = 7 THEN 'Jul'
                WHEN cps.current_month = 8 THEN 'Aug'
                WHEN cps.current_month = 9 THEN 'Sep'
                WHEN cps.current_month = 10 THEN 'Oct'
                WHEN cps.current_month = 11 THEN 'Nov'
                WHEN cps.current_month = 12 THEN 'Dec'
            END || ' ' || cps.current_year
        ELSE
            'Q' || cps.current_quarter || ' ' || cps.current_year
    END AS formatted_current_period
FROM current_payment_status cps;
-- v_payment_variance
CREATE VIEW v_payment_variance AS
SELECT
    ef.*,
    CASE
        WHEN ef.is_split = 1 THEN NULL  -- Mute variance for split payments
        WHEN ef.actual_fee IS NULL THEN NULL  -- No payment
        WHEN ef.expected_fee IS NULL THEN NULL  -- Can't calculate variance
        ELSE ROUND(ef.actual_fee - ef.expected_fee, 2)
    END AS variance_amount,
    CASE
        WHEN ef.is_split = 1 THEN NULL  -- Mute variance for split payments
        WHEN ef.actual_fee IS NULL THEN NULL  -- No payment
        WHEN ef.expected_fee IS NULL THEN NULL  -- Can't calculate variance
        WHEN ef.expected_fee = 0 THEN NULL  -- Avoid division by zero
        ELSE ROUND((ef.actual_fee - ef.expected_fee) / ef.expected_fee * 100, 2)
    END AS variance_percentage,
    CASE
        WHEN ef.is_split = 1 THEN NULL  -- Mute classification for split payments
        WHEN ef.actual_fee IS NULL THEN NULL  -- No payment
        WHEN ef.expected_fee IS NULL THEN NULL  -- Can't calculate
        WHEN ABS(ef.actual_fee - ef.expected_fee) <= 3 THEN 'Within Target'
        WHEN ef.actual_fee > ef.expected_fee THEN 'Overpaid'
        ELSE 'Underpaid'
    END AS variance_classification
FROM v_expected_fees ef;
-- v_payment_variance_with_estimates
CREATE VIEW v_payment_variance_with_estimates AS
SELECT
    ef.*,
    CASE
        WHEN ef.is_split = 1 THEN NULL  -- Mute variance for split payments
        WHEN ef.actual_fee IS NULL THEN NULL  -- No payment
        WHEN ef.estimated_expected_fee IS NULL THEN NULL  -- Can't calculate variance
        ELSE ROUND(ef.actual_fee - ef.estimated_expected_fee, 2)
    END AS variance_amount,
    CASE
        WHEN ef.is_split = 1 THEN NULL  -- Mute variance for split payments
        WHEN ef.actual_fee IS NULL THEN NULL  -- No payment
        WHEN ef.estimated_expected_fee IS NULL THEN NULL  -- Can't calculate variance
        WHEN ef.estimated_expected_fee = 0 THEN NULL  -- Avoid division by zero
        ELSE ROUND((ef.actual_fee - ef.estimated_expected_fee) / ef.estimated_expected_fee * 100, 2)
    END AS variance_percentage,
    CASE
        WHEN ef.is_split = 1 THEN NULL  -- Mute classification for split payments
        WHEN ef.actual_fee IS NULL THEN NULL  -- No payment
        WHEN ef.estimated_expected_fee IS NULL THEN NULL  -- Can't calculate
        WHEN ABS(ef.actual_fee - ef.estimated_expected_fee) <= 3 THEN 'Within Target'
        WHEN ef.actual_fee > ef.estimated_expected_fee THEN 'Overpaid'
        ELSE 'Underpaid'
    END AS variance_classification,
    ef.is_estimated_fee
FROM v_expected_fees_with_estimates ef;
-- v_payments_expanded
CREATE VIEW v_payments_expanded AS
WITH
-- Process monthly payments
monthly_payments AS (
    SELECT
        p.payment_id,
        p.client_id,
        p.contract_id,
        p.received_date,
        p.total_assets,
        p.actual_fee,
        p.applied_start_month,
        p.applied_start_month_year,
        p.applied_end_month,
        p.applied_end_month_year,
        (SELECT COUNT(*)
         FROM v_monthly_periods mp
         WHERE mp.client_id = p.client_id
         AND mp.period_key >= (p.applied_start_month_year * 100 + p.applied_start_month)
         AND mp.period_key <= (p.applied_end_month_year * 100 + p.applied_end_month)
        ) AS periods_covered,
        p.applied_start_month_year * 100 + p.applied_start_month AS start_period_key,
        p.applied_end_month_year * 100 + p.applied_end_month AS end_period_key,
        'monthly' AS schedule_type,
        CASE
            WHEN (p.applied_start_month_year <> p.applied_end_month_year) OR
                 (p.applied_start_month <> p.applied_end_month) THEN 1
            ELSE 0
        END AS is_split
    FROM payments p
    JOIN v_active_contracts c ON p.contract_id = c.contract_id
    WHERE p.valid_to IS NULL
    AND p.applied_start_month IS NOT NULL
    AND c.payment_schedule = 'monthly'
),
-- Process quarterly payments
quarterly_payments AS (
    SELECT
        p.payment_id,
        p.client_id,
        p.contract_id,
        p.received_date,
        p.total_assets,
        p.actual_fee,
        p.applied_start_quarter,
        p.applied_start_quarter_year,
        p.applied_end_quarter,
        p.applied_end_quarter_year,
        (SELECT COUNT(*)
         FROM v_quarterly_periods qp
         WHERE qp.client_id = p.client_id
         AND qp.period_key >= (p.applied_start_quarter_year * 10 + p.applied_start_quarter)
         AND qp.period_key <= (p.applied_end_quarter_year * 10 + p.applied_end_quarter)
        ) AS periods_covered,
        p.applied_start_quarter_year * 10 + p.applied_start_quarter AS start_period_key,
        p.applied_end_quarter_year * 10 + p.applied_end_quarter AS end_period_key,
        'quarterly' AS schedule_type,
        CASE
            WHEN (p.applied_start_quarter_year <> p.applied_end_quarter_year) OR
                 (p.applied_start_quarter <> p.applied_end_quarter) THEN 1
            ELSE 0
        END AS is_split
    FROM payments p
    JOIN v_active_contracts c ON p.contract_id = c.contract_id
    WHERE p.valid_to IS NULL
    AND p.applied_start_quarter IS NOT NULL
    AND c.payment_schedule = 'quarterly'
)
-- Combine and expand monthly payments to periods
SELECT
    p.payment_id,
    p.client_id,
    p.contract_id,
    p.received_date,
    p.total_assets,
    CASE
        WHEN p.is_split = 1 THEN p.actual_fee / p.periods_covered
        ELSE p.actual_fee
    END AS period_fee,
    p.actual_fee AS total_fee,
    mp.year,
    mp.month,
    NULL AS quarter,
    p.schedule_type,
    mp.period_key,
    p.is_split,
    p.start_period_key,
    p.end_period_key,
    p.periods_covered
FROM monthly_payments p
JOIN v_monthly_periods mp ON p.client_id = mp.client_id
WHERE mp.period_key >= p.start_period_key
AND mp.period_key <= p.end_period_key
UNION ALL
-- Combine and expand quarterly payments to periods
SELECT
    p.payment_id,
    p.client_id,
    p.contract_id,
    p.received_date,
    p.total_assets,
    CASE
        WHEN p.is_split = 1 THEN p.actual_fee / p.periods_covered
        ELSE p.actual_fee
    END AS period_fee,
    p.actual_fee AS total_fee,
    qp.year,
    NULL AS month,
    qp.quarter,
    p.schedule_type,
    qp.period_key,
    p.is_split,
    p.start_period_key,
    p.end_period_key,
    p.periods_covered
FROM quarterly_payments p
JOIN v_quarterly_periods qp ON p.client_id = qp.client_id
WHERE qp.period_key >= p.start_period_key
AND qp.period_key <= p.end_period_key;
-- v_quarterly_periods
CREATE VIEW v_quarterly_periods AS
WITH
client_periods AS (
    SELECT
        c.client_id,
        c.contract_id,
        MIN(CASE WHEN p.applied_start_quarter IS NOT NULL
            THEN p.applied_start_quarter_year * 10 + p.applied_start_quarter
            ELSE NULL END) AS first_period,
        (SELECT cp.quarterly_year * 10 + cp.quarterly_quarter FROM v_current_period cp) AS current_period
    FROM v_active_contracts c
    LEFT JOIN payments p ON c.client_id = p.client_id AND p.valid_to IS NULL
    WHERE c.payment_schedule = 'quarterly'
    GROUP BY c.client_id, c.contract_id
)
SELECT
    cp.client_id,
    cp.contract_id,
    period / 10 AS year,
    period % 10 AS quarter,
    period AS period_key
FROM client_periods cp
JOIN (
    WITH RECURSIVE quarters(period) AS (
        SELECT MIN(first_period) FROM client_periods
        UNION ALL
        SELECT
            CASE
                WHEN period % 10 = 4 THEN (period / 10 + 1) * 10 + 1
                ELSE period + 1
            END
        FROM quarters
        WHERE period < (SELECT MAX(current_period) FROM client_periods)
    )
    SELECT period FROM quarters
) q
WHERE q.period >= cp.first_period
AND q.period <= cp.current_period;
-- INDEX DEFINITIONS
-- idx_payment_files_payment_id
CREATE INDEX idx_payment_files_payment_id ON payment_files(payment_id);
-- idx_payments_client_date
CREATE INDEX idx_payments_client_date ON payments(client_id, received_date);
-- idx_payments_received_date
CREATE INDEX idx_payments_received_date ON payments(received_date);
-- idx_payments_valid_to
CREATE INDEX idx_payments_valid_to ON payments(valid_to);