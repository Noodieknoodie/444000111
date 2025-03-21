#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
401K Payment Database Audit Tool - Concise Output Version
Analyzes payment patterns and produces a bottom-line summary report.
"""

import sqlite3
import os
import datetime
import statistics
from collections import Counter
from dateutil.relativedelta import relativedelta
import warnings
warnings.filterwarnings('ignore')

# Configuration
DB_PATH = r"C:\CODING\OK_401K\backend\data\401k_payments.db"
OUTPUT_DIR = r"C:\CODING\OK_401K\backend\data"
OUTPUT_FILE = "401k_payment_audit_summary.txt"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Core analysis functions remain the same as in the verbose version
def calculate_date_gaps(dates):
    if not dates or len(dates) < 2:
        return []
    date_objects = [datetime.datetime.strptime(d, '%Y-%m-%d').date() if isinstance(d, str) else d for d in dates]
    date_objects.sort()
    gaps = [(date_objects[i+1] - date_objects[i]).days for i in range(len(date_objects)-1)]
    return gaps

def infer_payment_schedule(dates):
    if not dates or len(dates) < 3:
        return {"schedule": "Unknown", "confidence": 0}
    
    gaps = calculate_date_gaps(dates)
    avg_gap = sum(gaps) / len(gaps)
    
    monthly_gaps = [g for g in gaps if 25 <= g <= 35]
    quarterly_gaps = [g for g in gaps if 85 <= g <= 95]
    
    monthly_pct = len(monthly_gaps) / len(gaps) if gaps else 0
    quarterly_pct = len(quarterly_gaps) / len(gaps) if gaps else 0
    
    if monthly_pct > quarterly_pct:
        return {"schedule": "Monthly", "confidence": monthly_pct}
    else:
        return {"schedule": "Quarterly", "confidence": quarterly_pct}

def infer_fee_structure(payments, aum_values):
    if not payments or len(payments) < 2:
        return {"structure": "Unknown", "inferred_rate": None}
    
    # Check payment consistency
    payment_std = statistics.stdev(payments) if len(payments) > 1 else float('inf')
    payment_mean = statistics.mean(payments)
    payment_cv = payment_std / payment_mean if payment_mean > 0 else float('inf')
    
    # Check if we have enough AUM data
    payments_with_aum = [(p, a) for p, a in zip(payments, aum_values) if a is not None and a > 0]
    
    if len(payments_with_aum) < 2:
        # Not enough AUM data, use payment consistency
        if payment_cv < 0.1:
            return {"structure": "Flat", "inferred_rate": payment_mean}
        else:
            return {"structure": "Unknown", "inferred_rate": None}
    
    # Calculate percentage rates
    rates = [payment / aum for payment, aum in payments_with_aum]
    rate_std = statistics.stdev(rates) if len(rates) > 1 else float('inf')
    rate_mean = statistics.mean(rates)
    rate_cv = rate_std / rate_mean if rate_mean > 0 else float('inf')
    
    # Compare consistency
    if rate_cv < payment_cv:
        return {"structure": "Percentage", "inferred_rate": rate_mean}
    else:
        return {"structure": "Flat", "inferred_rate": payment_mean}

def detect_missing_payments(dates, inferred_schedule):
    if not dates or len(dates) < 2 or inferred_schedule["schedule"] == "Unknown":
        return {"missing_count": 0}
    
    date_objects = [datetime.datetime.strptime(d, '%Y-%m-%d').date() if isinstance(d, str) else d for d in dates]
    date_objects.sort()
    
    first_date = date_objects[0]
    last_date = date_objects[-1]
    
    # Generate expected dates
    expected_dates = []
    current_date = first_date
    
    if inferred_schedule["schedule"] == "Monthly":
        while current_date <= last_date:
            expected_dates.append(current_date)
            current_date += relativedelta(months=1)
    else:  # Quarterly
        while current_date <= last_date:
            expected_dates.append(current_date)
            current_date += relativedelta(months=3)
    
    # Find missing dates (allow 15-day window)
    missing_dates = []
    for expected_date in expected_dates:
        if not any(abs((actual_date - expected_date).days) <= 15 for actual_date in date_objects):
            missing_dates.append(expected_date)
    
    return {"missing_count": len(missing_dates)}

def format_currency(amount):
    if amount is None:
        return "N/A"
    return f"${amount:,.2f}"

def format_percentage(value):
    if value is None:
        return "N/A"
    if abs(value) < 0.01:
        return f"{value*100:.4f}%"
    return f"{value*100:.2f}%"

def analyze_database():
    """Main function to analyze the 401K payment database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all active client-contract combinations
        cursor.execute("""
            SELECT c.client_id, c.display_name, co.contract_id, co.provider_name
            FROM clients c
            JOIN contracts co ON c.client_id = co.client_id
            WHERE c.valid_to IS NULL AND co.valid_to IS NULL AND co.is_active = 1
            ORDER BY c.display_name
        """)
        clients = cursor.fetchall()
        
        # Report headers
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("         401K PAYMENT SYSTEM - AUDIT SUMMARY REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Issues overview table
        issues_table = []
        issues_table.append("| CLIENT                | SCHED | FEE  | MISS | LAST PAYMENT   | INFERRED RATE      |")
        issues_table.append("|----------------------|-------|------|------|---------------|-------------------|")
        
        for client in clients:
            client_id = client["client_id"]
            client_name = client["display_name"]
            contract_id = client["contract_id"]
            
            # Get database settings
            cursor.execute("""
                SELECT payment_schedule, fee_type, percent_rate, flat_rate
                FROM contracts
                WHERE client_id = ? AND contract_id = ? AND valid_to IS NULL
            """, (client_id, contract_id))
            db_settings = cursor.fetchone()
            
            if not db_settings:
                continue
                
            db_schedule = db_settings["payment_schedule"].capitalize() if db_settings["payment_schedule"] else "?"
            db_fee_type = db_settings["fee_type"].capitalize() if db_settings["fee_type"] else "?"
            
            # Get payments
            cursor.execute("""
                SELECT received_date, total_assets, actual_fee
                FROM payments
                WHERE client_id = ? AND contract_id = ? AND valid_to IS NULL
                ORDER BY received_date
            """, (client_id, contract_id))
            payments = cursor.fetchall()
            
            if not payments:
                issues_table.append(f"| {client_name[:20]:20} | NO PAYMENTS FOUND                               |")
                continue
            
            # Extract payment data
            payment_dates = [p["received_date"] for p in payments]
            payment_amounts = [p["actual_fee"] for p in payments]
            aum_values = [p["total_assets"] for p in payments]
            last_payment_date = payment_dates[-1] if payment_dates else "N/A"
            
            # Analysis
            inferred_schedule = infer_payment_schedule(payment_dates)
            inferred_fee = infer_fee_structure(payment_amounts, aum_values)
            missing_analysis = detect_missing_payments(payment_dates, inferred_schedule)
            
            # Detect mismatches
            schedule_status = "✓" if inferred_schedule["schedule"].startswith(db_schedule) else "❌"
            
            fee_status = "?"
            if inferred_fee["structure"] == "Unknown":
                fee_status = "?"
            elif (inferred_fee["structure"] == "Percentage" and db_fee_type == "Percentage") or \
                 (inferred_fee["structure"] == "Flat" and db_fee_type == "Flat"):
                fee_status = "✓"
            else:
                fee_status = "❌"
            
            # Format inferred rate
            if inferred_fee["structure"] == "Percentage" and inferred_fee["inferred_rate"] is not None:
                inferred_rate_str = format_percentage(inferred_fee["inferred_rate"])
            elif inferred_fee["structure"] == "Flat" and inferred_fee["inferred_rate"] is not None:
                inferred_rate_str = format_currency(inferred_fee["inferred_rate"])
            else:
                inferred_rate_str = "Unknown"
            
            # Add to issues table
            client_name_trunc = client_name[:20]
            missing_str = str(missing_analysis["missing_count"])
            
            issues_table.append(f"| {client_name_trunc:20} | {schedule_status:5} | {fee_status:4} | {missing_str:4} | {last_payment_date:13} | {inferred_rate_str:17} |")
        
        # Add issues table to report
        report_lines.extend(issues_table)
        report_lines.append("")
        report_lines.append("LEGEND:")
        report_lines.append("SCHED: Payment Schedule (✓=matches DB, ❌=mismatch)")
        report_lines.append("FEE: Fee Structure (✓=matches DB, ❌=mismatch)")
        report_lines.append("MISS: Number of potentially missed payments")
        
        # Add most critical issues section
        report_lines.append("")
        report_lines.append("CRITICAL ISSUES:")
        report_lines.append("-" * 80)
        
        # Extract clients with issues
        clients_with_schedule_mismatch = [line.split('|')[1].strip() for line in issues_table[2:] if "❌" in line.split('|')[2]]
        clients_with_fee_mismatch = [line.split('|')[1].strip() for line in issues_table[2:] if "❌" in line.split('|')[3]]
        clients_with_many_missing = []
        
        for line in issues_table[2:]:
            if "NO PAYMENTS" not in line:
                columns = line.split('|')
                client = columns[1].strip()
                missing = columns[4].strip()
                try:
                    if int(missing) >= 3:  # Consider 3+ missing payments significant
                        clients_with_many_missing.append(f"{client} ({missing} missing)")
                except:
                    pass
        
        if clients_with_schedule_mismatch:
            report_lines.append("Schedule Mismatches:")
            for client in clients_with_schedule_mismatch[:5]:  # Show top 5
                report_lines.append(f"  - {client}")
            if len(clients_with_schedule_mismatch) > 5:
                report_lines.append(f"  ... and {len(clients_with_schedule_mismatch)-5} more")
        
        if clients_with_fee_mismatch:
            report_lines.append("Fee Structure Mismatches:")
            for client in clients_with_fee_mismatch[:5]:  # Show top 5
                report_lines.append(f"  - {client}")
            if len(clients_with_fee_mismatch) > 5:
                report_lines.append(f"  ... and {len(clients_with_fee_mismatch)-5} more")
        
        if clients_with_many_missing:
            report_lines.append("Significant Missing Payments:")
            for client in clients_with_many_missing[:5]:  # Show top 5
                report_lines.append(f"  - {client}")
            if len(clients_with_many_missing) > 5:
                report_lines.append(f"  ... and {len(clients_with_many_missing)-5} more")
        
        # Write report to file
        output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        print(f"Summary analysis complete. Report saved to {output_path}")
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error during database analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    analyze_database()