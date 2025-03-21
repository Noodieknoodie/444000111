"""
Simplified diagnostic script to identify payment history endpoint issues.
"""
import sqlite3
import json
from pydantic import BaseModel, ValidationError
from typing import Optional, List
from enum import Enum

# Define an Enum for variance classification to avoid validation errors
class VarianceClassification(str, Enum):
    OVERPAID = "Overpaid"
    UNDERPAID = "Underpaid"
    WITHIN_TARGET = "Within Target"

# Define the model with exact field requirements
class PaymentHistoryModel(BaseModel):
    payment_id: int
    client_id: int
    display_name: str
    payment_date_formatted: str
    period_start_formatted: str
    period_end_formatted: Optional[str] = None
    aum: Optional[int] = None
    displayed_aum: Optional[int] = None
    is_estimated_aum: bool = False
    expected_fee: Optional[float] = None
    displayed_expected_fee: Optional[float] = None
    is_estimated_fee: bool = False
    actual_fee: float
    variance_amount: Optional[float] = None
    variance_classification: Optional[VarianceClassification] = None
    is_split: bool
    estimated_variance_amount: Optional[float] = None
    estimated_variance_classification: Optional[VarianceClassification] = None
    file_id: Optional[int] = None
    file_name: Optional[str] = None
    onedrive_path: Optional[str] = None
    method: Optional[str] = None
    notes: Optional[str] = None

def get_db_connection():
    """Connect to the database"""
    conn = sqlite3.connect("data/401k_payments_66.db")
    conn.row_factory = sqlite3.Row
    return conn

def test_payment_history():
    """Direct test of the payment history data"""
    print("=" * 50)
    print("PAYMENT HISTORY DIRECT TEST")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT * FROM v_payment_history WHERE client_id = 1 LIMIT 1").fetchall()
        
        if not rows:
            print("No data found for client_id=1")
            return
            
        row = rows[0]
        row_dict = dict(row)
        
        print("Raw data for first payment record:")
        print("-" * 50)
        
        # Convert and print each field with its type
        for key, value in row_dict.items():
            print(f"{key}: {value} ({type(value).__name__})")
        
        print("\nTrying to convert and validate this record...")
        print("-" * 50)
        
        # Try to convert problematic fields one by one
        converted = {}
        
        # Handle boolean fields
        for field in ['is_split', 'is_estimated_aum', 'is_estimated_fee']:
            try:
                converted[field] = bool(row_dict.get(field, 0))
                print(f"✓ {field}: Successfully converted to bool: {converted[field]}")
            except Exception as e:
                print(f"✗ ERROR: {field} conversion failed: {str(e)}")
                return
                
        # Handle required string fields
        for field in ['display_name', 'payment_date_formatted', 'period_start_formatted']:
            if field not in row_dict or row_dict[field] is None:
                print(f"✗ ERROR: Required field {field} is missing or None")
                return
            converted[field] = row_dict[field]
            print(f"✓ {field}: Valid value: {converted[field]}")
            
        # Handle optional string fields
        for field in ['period_end_formatted', 'notes', 'method', 'onedrive_path', 'file_name']:
            converted[field] = row_dict.get(field)
            print(f"✓ {field}: Value: {converted[field]}")
            
        # Handle float fields
        for field in ['expected_fee', 'displayed_expected_fee', 'variance_amount', 'actual_fee', 'estimated_variance_amount']:
            try:
                value = row_dict.get(field)
                if value is not None:
                    converted[field] = float(value)
                    print(f"✓ {field}: Successfully converted to float: {converted[field]}")
                else:
                    converted[field] = None
                    # Only actual_fee is required
                    if field == 'actual_fee':
                        print(f"✗ ERROR: Required field {field} is None")
                        return
                    print(f"✓ {field}: None value is acceptable")
            except Exception as e:
                print(f"✗ ERROR: {field} conversion failed: {str(e)} (value was: {row_dict.get(field)})")
                return
                
        # Handle integer fields
        for field in ['payment_id', 'client_id', 'aum', 'displayed_aum', 'file_id']:
            try:
                value = row_dict.get(field)
                if value is not None:
                    if field in ['payment_id', 'client_id']:  # Required
                        converted[field] = int(value)
                        print(f"✓ {field}: Successfully converted to int: {converted[field]}")
                    else:  # Optional
                        converted[field] = int(value) if value else None
                        print(f"✓ {field}: Successfully converted to int: {converted[field]}")
                else:
                    converted[field] = None
                    if field in ['payment_id', 'client_id']:  # Required
                        print(f"✗ ERROR: Required field {field} is None")
                        return
                    print(f"✓ {field}: None value is acceptable")
            except Exception as e:
                print(f"✗ ERROR: {field} conversion failed: {str(e)} (value was: {row_dict.get(field)})")
                return
                
        # Handle enum fields
        for field in ['variance_classification', 'estimated_variance_classification']:
            try:
                value = row_dict.get(field)
                if value is not None:
                    if value not in ['Overpaid', 'Underpaid', 'Within Target']:
                        print(f"✗ ERROR: {field} has invalid value: {value}")
                        print(f"   Must be one of: Overpaid, Underpaid, Within Target")
                        return
                    converted[field] = value
                    print(f"✓ {field}: Valid enum value: {converted[field]}")
                else:
                    converted[field] = None
                    print(f"✓ {field}: None value is acceptable")
            except Exception as e:
                print(f"✗ ERROR: {field} processing failed: {str(e)}")
                return
                
        # Final validation with Pydantic
        try:
            model = PaymentHistoryModel(**converted)
            print("\n✓ RECORD PASSED VALIDATION!")
            print("-" * 50)
            
            # Print any missing fields from the original data
            missing_fields = set(model.__fields__.keys()) - set(row_dict.keys())
            if missing_fields:
                print("\nWARNING: These fields were missing from the database but set to defaults:")
                for field in missing_fields:
                    print(f"  - {field}")
                
        except ValidationError as e:
            print(f"\n✗ VALIDATION ERROR: {e}")
            
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
    finally:
        conn.close()
        
if __name__ == "__main__":
    test_payment_history()