# backend/test_endpoints.py
import requests
import json
from pprint import pprint
import sys

# Base URL for API
BASE_URL = "http://127.0.0.1:6069/api"

# Colors for console output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

def test_endpoint(method, endpoint, payload=None, files=None):
    """Test an API endpoint and return the result"""
    url = f"{BASE_URL}/{endpoint}"
    
    print(f"{Colors.BLUE}Testing {method} {url}{Colors.ENDC}")
    
    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            if files:
                response = requests.post(url, data=payload, files=files)
            else:
                response = requests.post(url, json=payload)
        elif method.upper() == "PUT":
            response = requests.put(url, json=payload)
        elif method.upper() == "DELETE":
            response = requests.delete(url)
        else:
            print(f"{Colors.RED}Unsupported method: {method}{Colors.ENDC}")
            return False, None
        
        # Check if response is successful
        if response.status_code < 400:
            print(f"{Colors.GREEN}Success: {response.status_code}{Colors.ENDC}")
            if response.content and len(response.content) > 0:
                try:
                    data = response.json()
                    # For list responses, just show count and first item
                    if isinstance(data, list):
                        print(f"Received {len(data)} items")
                        if len(data) > 0:
                            print("First item:")
                            pprint(data[0])
                    else:
                        pprint(data)
                except json.JSONDecodeError:
                    print(f"Non-JSON response: {response.content[:100]}...")
            return True, response
        else:
            print(f"{Colors.RED}Error {response.status_code}: {response.content}{Colors.ENDC}")
            return False, response
    except Exception as e:
        print(f"{Colors.RED}Exception: {str(e)}{Colors.ENDC}")
        return False, None

def main():
    """Run tests on all endpoints"""
    results = {}
    
    # Health check
    results["health"] = test_endpoint("GET", "../health")
    
    # Client endpoints
    results["clients_sidebar"] = test_endpoint("GET", "clients/sidebar")
    
    # Get a client ID to use for further tests
    success, resp = results["clients_sidebar"]
    if success and resp.json() and len(resp.json()) > 0:
        client_id = resp.json()[0]["client_id"]
        print(f"\n{Colors.YELLOW}Using client_id: {client_id} for further tests{Colors.ENDC}\n")
        
        # Client detail endpoints
        results["client_detail"] = test_endpoint("GET", f"clients/{client_id}")
        results["client_details_view"] = test_endpoint("GET", f"clients/details/{client_id}")
        
        # Contract endpoints
        results["contract_active"] = test_endpoint("GET", f"contracts/active/{client_id}")
        results["client_contracts"] = test_endpoint("GET", f"contracts/client/{client_id}")
        
        # Get a contract ID for further tests
        if results["client_contracts"][0] and results["client_contracts"][1].json():
            contract_id = results["client_contracts"][1].json()[0]["contract_id"]
            print(f"\n{Colors.YELLOW}Using contract_id: {contract_id} for further tests{Colors.ENDC}\n")
        else:
            contract_id = None
        
        # Payment endpoints
        results["payment_history"] = test_endpoint("GET", f"payments/history/{client_id}")
        results["payment_last"] = test_endpoint("GET", f"payments/last/{client_id}")
        results["payment_missing"] = test_endpoint("GET", f"payments/missing/{client_id}")
        
        # Contact endpoints
        results["contacts"] = test_endpoint("GET", f"contacts/client/{client_id}")
    else:
        print(f"{Colors.RED}No clients found to test with!{Colors.ENDC}")
    
    # Print summary
    print("\n" + "="*50)
    print(f"{Colors.BLUE}TEST SUMMARY:{Colors.ENDC}")
    print("="*50)
    
    success_count = 0
    failure_count = 0
    
    for name, (success, _) in results.items():
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if success else f"{Colors.RED}FAIL{Colors.ENDC}"
        print(f"{name:30} {status}")
        
        if success:
            success_count += 1
        else:
            failure_count += 1
    
    print("="*50)
    print(f"Total: {success_count + failure_count}, Passed: {success_count}, Failed: {failure_count}")
    print("="*50)
    
    # Return exit code based on success/failure
    if failure_count > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())