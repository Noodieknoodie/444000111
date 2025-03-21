#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
401K Payment Database Audit Tool

This script analyzes payment patterns in the 401K database to detect:
- Actual payment frequency (monthly vs quarterly)
- Fee structure (inferred from payment/AUM relationship)
- Missing payments
- Payment irregularities
- Differences between actual patterns and database settings

Output is saved to a formatted text file with detailed findings.
"""

import sqlite3
import os
import datetime
import statistics
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from dateutil.relativedelta import relativedelta
import math
import warnings
warnings.filterwarnings('ignore')

# Configuration
DB_PATH = r"C:\CODING\OK_401K\backend\data\401k_payments.db"
OUTPUT_DIR = r"C:\CODING\OK_401K\backend\data"
OUTPUT_FILE = "401k_payment_audit_report.txt"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Utility Functions
def safe_float_convert(val):
    """Safely convert a value to float, handling special cases."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    # Handle special string values
    if isinstance(val, str):
        val = val.strip()
        if val in ('', '-', 'N/A', 'None', 'null'):
            return None
        try:
            return float(val)
        except ValueError:
            return None
    return None

def safe_date_convert(val):
    """Safely convert a value to date, handling special cases."""
    if val is None:
        return None
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        val = val.strip()
        if val in ('', '-', 'N/A', 'None', 'null'):
            return None
        try:
            return datetime.datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            try:
                # Try alternate date formats if the standard one fails
                return datetime.datetime.strptime(val, '%m/%d/%Y').date()
            except ValueError:
                return None
    return None

def format_currency(amount):
    """Format a number as currency with commas."""
    if amount is None:
        return "N/A"
    try:
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        return "N/A"

def format_percentage(value):
    """Format a number as percentage with appropriate decimals."""
    if value is None:
        return "N/A"
    try:
        value = float(value)
        # Use 4 decimals for values under 1%, otherwise 2
        if abs(value) < 0.01:
            return f"{value*100:.4f}%"
        return f"{value*100:.2f}%"
    except (ValueError, TypeError):
        return "N/A"

def calculate_date_gaps(dates):
    """Calculate gaps between consecutive dates in days."""
    if not dates or len(dates) < 2:
        return []
        
    # Convert dates to date objects and filter out None values
    date_objects = []
    for d in dates:
        date_obj = safe_date_convert(d)
        if date_obj is not None:
            date_objects.append(date_obj)
    
    if len(date_objects) < 2:
        return []
        
    date_objects.sort()
    
    # Calculate gaps in days
    gaps = [(date_objects[i+1] - date_objects[i]).days for i in range(len(date_objects)-1)]
    return gaps

def infer_payment_schedule(dates):
    """Infer whether payments are monthly or quarterly based on date patterns."""
    if not dates or len(dates) < 3:
        return {"schedule": "Unknown", "confidence": 0, "avg_gap": None}
    
    gaps = calculate_date_gaps(dates)
    
    if not gaps:
        return {"schedule": "Unknown", "confidence": 0, "avg_gap": None}
        
    avg_gap = sum(gaps) / len(gaps)
    
    # Categorize gaps by typical payment periods
    monthly_gaps = [g for g in gaps if 25 <= g <= 35]  # ~30 days
    quarterly_gaps = [g for g in gaps if 85 <= g <= 95]  # ~90 days
    
    # Special case for COVID-related larger gaps
    potential_double_monthly = [g for g in gaps if 55 <= g <= 65]  # ~60 days (missed a month)
    potential_double_quarterly = [g for g in gaps if 175 <= g <= 185]  # ~180 days (missed a quarter)
    
    # Calculate metrics
    monthly_pct = len(monthly_gaps) / len(gaps) if gaps else 0
    quarterly_pct = len(quarterly_gaps) / len(gaps) if gaps else 0
    double_monthly_pct = len(potential_double_monthly) / len(gaps) if gaps else 0
    double_quarterly_pct = len(potential_double_quarterly) / len(gaps) if gaps else 0
    
    # Adjust for potential doubles
    adjusted_monthly_pct = monthly_pct + (double_monthly_pct * 0.5)
    adjusted_quarterly_pct = quarterly_pct + (double_quarterly_pct * 0.5)
    
    # Determine schedule
    if adjusted_monthly_pct > adjusted_quarterly_pct:
        confidence = adjusted_monthly_pct
        schedule = "Monthly"
    else:
        confidence = adjusted_quarterly_pct
        schedule = "Quarterly"
    
    # Check if there's really not enough evidence
    if confidence < 0.3:
        schedule = "Irregular"
        
    return {
        "schedule": schedule,
        "confidence": confidence,
        "avg_gap": avg_gap,
        "monthly_pct": monthly_pct,
        "quarterly_pct": quarterly_pct,
        "gap_analysis": Counter([round(g/30) for g in gaps])  # Gaps in months (rounded)
    }

def infer_fee_structure(payments, aum_values):
    """Determine if payments follow a flat fee or percentage of AUM."""
    if not payments or len(payments) < 2:
        return {"structure": "Unknown", "confidence": 0, "inferred_rate": None}
    
    # Convert values to floats and handle edge cases
    clean_payments = []
    clean_aum_values = []
    
    for p, a in zip(payments, aum_values):
        payment = safe_float_convert(p)
        aum = safe_float_convert(a)
        
        if payment is not None:
            clean_payments.append(payment)
            
        if payment is not None and aum is not None and aum > 0:
            clean_aum_values.append((payment, aum))
    
    if len(clean_payments) < 2:
        return {"structure": "Unknown", "confidence": 0, "inferred_rate": None}
    
    # Check if we have enough AUM data to analyze
    if len(clean_aum_values) < 2:
        # Not enough AUM data, check payment consistency
        try:
            payment_std = statistics.stdev(clean_payments)
            payment_mean = statistics.mean(clean_payments)
            coefficient_variation = payment_std / payment_mean if payment_mean > 0 else float('inf')
            
            if coefficient_variation < 0.05:  # Very consistent payments
                return {
                    "structure": "Flat",
                    "confidence": 0.9,
                    "inferred_rate": payment_mean,
                    "consistency": "High",
                    "cv": coefficient_variation
                }
            elif coefficient_variation < 0.15:  # Somewhat consistent
                return {
                    "structure": "Likely Flat",
                    "confidence": 0.7,
                    "inferred_rate": payment_mean,
                    "consistency": "Medium",
                    "cv": coefficient_variation
                }
            else:
                return {
                    "structure": "Variable",
                    "confidence": 0.5,
                    "inferred_rate": None,
                    "consistency": "Low",
                    "cv": coefficient_variation
                }
        except statistics.StatisticsError:
            return {"structure": "Unknown", "confidence": 0, "inferred_rate": None}
    
    # We have AUM data, check fee as percentage
    try:
        rates = [payment / aum for payment, aum in clean_aum_values]
        
        if not rates or len(rates) < 2:
            return {
                "structure": "Variable",
                "confidence": 0.5,
                "inferred_rate": None,
                "consistency": "Low",
                "cv": float('inf')
            }
        
        rate_std = statistics.stdev(rates)
        rate_mean = statistics.mean(rates)
        rate_cv = rate_std / rate_mean if rate_mean > 0 else float('inf')
        
        # Re-calculate payment consistency for comparison
        payment_std = statistics.stdev(clean_payments)
        payment_mean = statistics.mean(clean_payments)
        payment_cv = payment_std / payment_mean if payment_mean > 0 else float('inf')
        
        if rate_cv < 0.1:  # Consistent percentage
            return {
                "structure": "Percentage",
                "confidence": 0.9,
                "inferred_rate": rate_mean,
                "consistency": "High",
                "cv": rate_cv
            }
        elif rate_cv < 0.25:  # Somewhat consistent percentage
            return {
                "structure": "Likely Percentage",
                "confidence": 0.7,
                "inferred_rate": rate_mean,
                "consistency": "Medium",
                "cv": rate_cv
            }
        elif payment_cv < rate_cv:
            return {
                "structure": "Likely Flat",
                "confidence": 0.6,
                "inferred_rate": payment_mean,
                "consistency": "Medium",
                "cv": payment_cv
            }
        else:
            return {
                "structure": "Likely Percentage",
                "confidence": 0.6,
                "inferred_rate": rate_mean,
                "consistency": "Medium",
                "cv": rate_cv
            }
    except (statistics.StatisticsError, ZeroDivisionError):
        return {"structure": "Unknown", "confidence": 0, "inferred_rate": None}

def detect_missing_payments(dates, inferred_schedule):
    """Identify potentially missing payments based on inferred schedule."""
    if not dates or len(dates) < 2 or inferred_schedule["schedule"] == "Unknown" or inferred_schedule["schedule"] == "Irregular":
        return {"missing_dates": [], "potential_missing_count": 0, "expected_dates": []}
    
    # Convert dates to datetime objects, filter out None values, and sort
    date_objects = []
    for d in dates:
        date_obj = safe_date_convert(d)
        if date_obj is not None:
            date_objects.append(date_obj)
    
    if len(date_objects) < 2:
        return {"missing_dates": [], "potential_missing_count": 0, "expected_dates": []}
        
    date_objects.sort()
    
    first_date = date_objects[0]
    last_date = date_objects[-1]
    
    # Generate expected payment dates based on inferred schedule
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
    
    # Find missing dates (allow 15-day window for matching)
    missing_dates = []
    for expected_date in expected_dates:
        if not any(abs((actual_date - expected_date).days) <= 15 for actual_date in date_objects):
            missing_dates.append(expected_date)
    
    return {
        "missing_dates": missing_dates,
        "potential_missing_count": len(missing_dates),
        "expected_dates": expected_dates
    }

def analyze_payment_makeup(payment_data, missing_data):
    """Analyze if missing payments were made up later."""
    if not payment_data or not missing_data or not missing_data.get("missing_dates"):
        return {"makeup_detected": False, "makeup_payments": []}
    
    # Clean up data - convert dates and amounts to proper formats
    clean_payment_data = []
    for p in payment_data:
        date = safe_date_convert(p.get("date"))
        amount = safe_float_convert(p.get("amount"))
        
        if date is not None:
            clean_payment_data.append({
                "date": date,
                "amount": amount,
                "id": p.get("id")
            })
    
    if not clean_payment_data:
        return {"makeup_detected": False, "makeup_payments": []}
    
    # Extract clean amounts for average calculation
    amounts = [p["amount"] for p in clean_payment_data if p["amount"] is not None]
    
    if not amounts:
        return {"makeup_detected": False, "makeup_payments": []}
    
    try:
        # Calculate average payment
        avg_payment = statistics.mean(amounts)
        
        # Look for payments significantly larger than average (potential makeup)
        potential_makeup = []
        for p in clean_payment_data:
            if p["amount"] is None:
                continue
                
            # Check if payment is significantly larger than average (>1.8x)
            if p["amount"] > avg_payment * 1.8:
                # Look for missing dates within 60 days before this payment
                nearby_missing = [
                    md for md in missing_data["missing_dates"] 
                    if 0 < (p["date"] - md).days <= 60
                ]
                
                if nearby_missing:
                    potential_makeup.append({
                        "date": p["date"],
                        "amount": p["amount"],
                        "avg_ratio": p["amount"] / avg_payment,
                        "potential_makeup_for": nearby_missing
                    })
        
        return {
            "makeup_detected": len(potential_makeup) > 0,
            "makeup_payments": potential_makeup
        }
    except statistics.StatisticsError:
        return {"makeup_detected": False, "makeup_payments": []}

def get_actual_db_settings(conn, client_id, contract_id):
    """Retrieve the actual settings from the database for comparison."""
    query = """
    SELECT 
        c.display_name,
        co.payment_schedule,
        co.fee_type,
        co.percent_rate,
        co.flat_rate,
        co.num_people
    FROM 
        contracts co
    JOIN
        clients c ON co.client_id = c.client_id
    WHERE 
        co.client_id = ? AND co.contract_id = ? AND co.valid_to IS NULL
    """
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, (client_id, contract_id))
        result = cursor.fetchone()
        
        if result:
            return {
                "client_name": result[0],
                "payment_schedule": result[1],
                "fee_type": result[2],
                "percent_rate": safe_float_convert(result[3]),
                "flat_rate": safe_float_convert(result[4]),
                "num_people": result[5]
            }
        else:
            return None
    except Exception as e:
        print(f"Error retrieving DB settings: {e}")
        return None

def analyze_database():
    """Main function to analyze the 401K payment database."""
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Get all active client-contract combinations
        client_query = """
        SELECT 
            c.client_id, 
            c.display_name,
            co.contract_id,
            co.provider_name
        FROM 
            clients c
        JOIN 
            contracts co ON c.client_id = co.client_id
        WHERE 
            c.valid_to IS NULL AND co.valid_to IS NULL AND co.is_active = 1
        ORDER BY 
            c.display_name
        """
        
        cursor = conn.cursor()
        cursor.execute(client_query)
        clients = cursor.fetchall()
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("             401K PAYMENT SYSTEM - DATABASE AUDIT REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Database: {DB_PATH}")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append("SUMMARY OF FINDINGS")
        report_lines.append("-" * 80)
        
        # Track summary statistics
        total_clients = len(clients)
        schedule_mismatches = 0
        fee_structure_mismatches = 0
        clients_with_missing_payments = 0
        total_missing_payments = 0
        clients_with_makeup_payments = 0
        
        # Store detailed findings for each client
        client_findings = []
        
        # Analyze each client-contract pair
        for client in clients:
            client_id = client["client_id"]
            contract_id = client["contract_id"]
            client_name = client["display_name"]
            provider_name = client["provider_name"]
            
            # Get actual settings from database
            db_settings = get_actual_db_settings(conn, client_id, contract_id)
            
            # Get all payments for this client-contract
            payment_query = """
            SELECT 
                payment_id, 
                received_date, 
                total_assets, 
                actual_fee,
                method,
                notes,
                applied_start_month,
                applied_start_month_year,
                applied_start_quarter,
                applied_start_quarter_year
            FROM 
                payments 
            WHERE 
                client_id = ? AND contract_id = ? AND valid_to IS NULL
            ORDER BY 
                received_date
            """
            
            cursor.execute(payment_query, (client_id, contract_id))
            payments = cursor.fetchall()
            
            # Skip if no payments
            if not payments:
                client_findings.append({
                    "client_id": client_id,
                    "client_name": client_name,
                    "contract_id": contract_id,
                    "provider_name": provider_name,
                    "status": "No payments found",
                    "payment_count": 0,
                    "db_settings": db_settings,
                    "inferred_schedule": {"schedule": "Unknown"},
                    "inferred_fee": {"structure": "Unknown"}
                })
                continue
            
            # Extract payment data
            payment_dates = [p["received_date"] for p in payments]
            payment_amounts = [p["actual_fee"] for p in payments]
            aum_values = [p["total_assets"] for p in payments]
            
            payment_data = [
                {
                    "id": p["payment_id"],
                    "date": p["received_date"],
                    "amount": p["actual_fee"],
                    "aum": p["total_assets"],
                    "method": p["method"],
                    "notes": p["notes"],
                    "month": p["applied_start_month"],
                    "month_year": p["applied_start_month_year"],
                    "quarter": p["applied_start_quarter"],
                    "quarter_year": p["applied_start_quarter_year"]
                }
                for p in payments
            ]
            
            # Analyze payment schedule
            inferred_schedule = infer_payment_schedule(payment_dates)
            
            # Analyze fee structure
            inferred_fee = infer_fee_structure(payment_amounts, aum_values)
            
            # Analyze missing payments
            missing_analysis = detect_missing_payments(payment_dates, inferred_schedule)
            
            # Analyze potential makeup payments
            makeup_analysis = analyze_payment_makeup(payment_data, missing_analysis)
            
            # Check for mismatches with database settings
            schedule_mismatch = False
            fee_structure_mismatch = False
            
            if db_settings:
                # Schedule mismatch check
                if db_settings["payment_schedule"] and inferred_schedule["schedule"] != "Unknown" and inferred_schedule["schedule"] != "Irregular":
                    db_schedule = db_settings["payment_schedule"].capitalize() if db_settings["payment_schedule"] else ""
                    inferred_schedule_name = inferred_schedule["schedule"]
                    
                    if db_schedule != inferred_schedule_name:
                        schedule_mismatch = True
                        schedule_mismatches += 1
                
                # Fee structure mismatch check
                if db_settings["fee_type"] and inferred_fee["structure"] != "Unknown" and inferred_fee["structure"] != "Variable":
                    db_fee_type = db_settings["fee_type"].capitalize() if db_settings["fee_type"] else ""
                    
                    if "Percentage" in inferred_fee["structure"] and db_fee_type != "Percentage":
                        fee_structure_mismatch = True
                        fee_structure_mismatches += 1
                    elif "Flat" in inferred_fee["structure"] and db_fee_type != "Flat":
                        fee_structure_mismatch = True
                        fee_structure_mismatches += 1
            
            # Update summary stats
            if missing_analysis.get("potential_missing_count", 0) > 0:
                clients_with_missing_payments += 1
                total_missing_payments += missing_analysis.get("potential_missing_count", 0)
            
            if makeup_analysis.get("makeup_detected", False):
                clients_with_makeup_payments += 1
            
            # Store client findings
            client_findings.append({
                "client_id": client_id,
                "client_name": client_name,
                "contract_id": contract_id,
                "provider_name": provider_name,
                "payment_count": len(payments),
                "first_payment": payment_dates[0] if payment_dates else None,
                "last_payment": payment_dates[-1] if payment_dates else None,
                "db_settings": db_settings,
                "inferred_schedule": inferred_schedule,
                "inferred_fee": inferred_fee,
                "missing_analysis": missing_analysis,
                "makeup_analysis": makeup_analysis,
                "schedule_mismatch": schedule_mismatch,
                "fee_structure_mismatch": fee_structure_mismatch
            })
        
        # Add summary statistics to report
        report_lines.append(f"Total Clients Analyzed: {total_clients}")
        report_lines.append(f"Clients with Schedule Mismatches: {schedule_mismatches}")
        report_lines.append(f"Clients with Fee Structure Mismatches: {fee_structure_mismatches}")
        report_lines.append(f"Clients with Missing Payments: {clients_with_missing_payments}")
        report_lines.append(f"Total Missing Payments: {total_missing_payments}")
        report_lines.append(f"Clients with Makeup Payments: {clients_with_makeup_payments}")
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Add client-specific sections for issues
        report_lines.append("DETAILED FINDINGS BY CLIENT")
        report_lines.append("=" * 80)
        
        # Sort findings: Issues first, then alphabetically by client name
        sorted_findings = sorted(
            client_findings, 
            key=lambda x: (
                not (x.get("schedule_mismatch", False) or x.get("fee_structure_mismatch", False)),
                x.get("missing_analysis", {}).get("potential_missing_count", 0) == 0,
                x.get("client_name", "")
            )
        )
        
        for client in sorted_findings:
            report_lines.append("")
            report_lines.append(f"CLIENT: {client['client_name']} (ID: {client['client_id']})")
            report_lines.append(f"Provider: {client['provider_name']} (Contract ID: {client['contract_id']})")
            report_lines.append("-" * 80)
            
            if client.get("payment_count", 0) == 0:
                report_lines.append("STATUS: No payments found for this client.")
                continue
            
            # Format dates for report
            first_payment = safe_date_convert(client.get("first_payment"))
            last_payment = safe_date_convert(client.get("last_payment"))
            first_payment_str = first_payment.strftime('%Y-%m-%d') if first_payment else "Unknown"
            last_payment_str = last_payment.strftime('%Y-%m-%d') if last_payment else "Unknown"
            
            report_lines.append(f"Payment History: {client['payment_count']} payments from {first_payment_str} to {last_payment_str}")
            
            # Payment schedule
            inferred_schedule = client.get("inferred_schedule", {"schedule": "Unknown"})
            report_lines.append("")
            report_lines.append("PAYMENT SCHEDULE ANALYSIS:")
            if inferred_schedule.get("schedule") == "Unknown" or inferred_schedule.get("schedule") == "Irregular":
                report_lines.append(f"  Inferred Schedule: {inferred_schedule.get('schedule')} (insufficient data for determination)")
            else:
                report_lines.append(f"  Inferred Schedule: {inferred_schedule.get('schedule')} (confidence: {inferred_schedule.get('confidence', 0):.2f})")
                if inferred_schedule.get("avg_gap") is not None:
                    report_lines.append(f"  Average Gap: {inferred_schedule.get('avg_gap'):.1f} days")
                if "gap_analysis" in inferred_schedule:
                    report_lines.append(f"  Gap Analysis: {dict(inferred_schedule['gap_analysis'])} (in months)")
                
                if client.get("db_settings"):
                    db_schedule = client["db_settings"].get("payment_schedule", "").capitalize() if client["db_settings"].get("payment_schedule") else "Not set"
                    report_lines.append(f"  Database Setting: {db_schedule}")
                    
                    if client.get("schedule_mismatch"):
                        report_lines.append(f"  ** MISMATCH DETECTED: Data suggests {inferred_schedule.get('schedule')}, database says {db_schedule}")
            
            # Fee structure
            inferred_fee = client.get("inferred_fee", {"structure": "Unknown"})
            report_lines.append("")
            report_lines.append("FEE STRUCTURE ANALYSIS:")
            if inferred_fee.get("structure") == "Unknown" or inferred_fee.get("structure") == "Variable":
                report_lines.append(f"  Inferred Structure: {inferred_fee.get('structure')} (insufficient data for determination)")
            else:
                report_lines.append(f"  Inferred Structure: {inferred_fee.get('structure')} (confidence: {inferred_fee.get('confidence', 0):.2f})")
                if "consistency" in inferred_fee and "cv" in inferred_fee:
                    report_lines.append(f"  Consistency: {inferred_fee.get('consistency')} (CV: {inferred_fee.get('cv'):.4f})")
                
                if "Percentage" in inferred_fee.get("structure", "") and inferred_fee.get("inferred_rate") is not None:
                    report_lines.append(f"  Inferred Rate: {format_percentage(inferred_fee.get('inferred_rate'))}")
                elif "Flat" in inferred_fee.get("structure", "") and inferred_fee.get("inferred_rate") is not None:
                    report_lines.append(f"  Inferred Amount: {format_currency(inferred_fee.get('inferred_rate'))}")
                
                if client.get("db_settings"):
                    db_fee_type = client["db_settings"].get("fee_type", "").capitalize() if client["db_settings"].get("fee_type") else "Not set"
                    report_lines.append(f"  Database Setting: {db_fee_type}")
                    
                    if db_fee_type == "Percentage" and client["db_settings"].get("percent_rate") is not None:
                        report_lines.append(f"  Database Rate: {format_percentage(client['db_settings'].get('percent_rate'))}")
                    elif db_fee_type == "Flat" and client["db_settings"].get("flat_rate") is not None:
                        report_lines.append(f"  Database Amount: {format_currency(client['db_settings'].get('flat_rate'))}")
                    
                    if client.get("fee_structure_mismatch"):
                        report_lines.append(f"  ** MISMATCH DETECTED: Data suggests {inferred_fee.get('structure')}, database says {db_fee_type}")
            
            # Missing payments
            missing_analysis = client.get("missing_analysis", {"missing_dates": [], "potential_missing_count": 0})
            report_lines.append("")
            report_lines.append("MISSING PAYMENT ANALYSIS:")
            if inferred_schedule.get("schedule") == "Unknown" or inferred_schedule.get("schedule") == "Irregular":
                report_lines.append("  Cannot determine missing payments (schedule unclear)")
            else:
                if missing_analysis.get("potential_missing_count", 0) == 0:
                    report_lines.append("  No missing payments detected")
                else:
                    report_lines.append(f"  Potential Missing Payments: {missing_analysis.get('potential_missing_count', 0)}")
                    missing_dates = missing_analysis.get("missing_dates", [])
                    if missing_dates:
                        # List up to 5 missing dates
                        max_missing_to_show = min(5, len(missing_dates))
                        missing_dates_str = ", ".join(d.strftime('%Y-%m-%d') for d in missing_dates[:max_missing_to_show])
                        if len(missing_dates) > max_missing_to_show:
                            missing_dates_str += f" (plus {len(missing_dates) - max_missing_to_show} more)"
                        report_lines.append(f"  Missing Dates: {missing_dates_str}")
            
            # Makeup payments
            makeup_analysis = client.get("makeup_analysis", {"makeup_detected": False, "makeup_payments": []})
            if makeup_analysis.get("makeup_detected"):
                report_lines.append("")
                report_lines.append("POTENTIAL MAKEUP PAYMENTS:")
                for payment in makeup_analysis.get("makeup_payments", []):
                    amount = payment.get("amount")
                    ratio = payment.get("avg_ratio")
                    payment_date = payment.get("date")
                    makeup_dates = payment.get("potential_makeup_for", [])
                    
                    if payment_date and amount is not None and ratio is not None and makeup_dates:
                        makeup_dates_str = ", ".join(d.strftime('%Y-%m-%d') for d in makeup_dates)
                        report_lines.append(f"  {payment_date.strftime('%Y-%m-%d')}: {format_currency(amount)} ({ratio:.1f}x avg) - may cover: {makeup_dates_str}")
        
        # Write report to file
        output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        print(f"Analysis complete. Report saved to {output_path}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error during database analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    analyze_database()