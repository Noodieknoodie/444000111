# backend/tests/test_api.py
import pytest
from fastapi.testclient import TestClient

def test_health_check(test_client):
    """Test that the health check endpoint returns healthy"""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_get_clients(test_client):
    """Test fetching clients endpoint"""
    response = test_client.get("/api/clients/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_client_sidebar(test_client):
    """Test fetching client sidebar data"""
    response = test_client.get("/api/clients/sidebar")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
    if len(response.json()) > 0:
        # Check that the sidebar item has expected fields
        sidebar_item = response.json()[0]
        assert "client_id" in sidebar_item
        assert "display_name" in sidebar_item
        assert "payment_status" in sidebar_item

def test_missing_payments(test_client, test_db):
    """Test fetching missing payments for a client"""
    # Get the first client_id from the database to test with
    client = test_db.execute("SELECT client_id FROM clients LIMIT 1").fetchone()
    
    if client:
        client_id = client["client_id"]
        response = test_client.get(f"/api/payments/missing/{client_id}")
        assert response.status_code == 200
        
        # Check that the response has the expected format
        missing_data = response.json()
        assert "client_id" in missing_data
        assert "display_name" in missing_data
        assert "missing_periods" in missing_data

def test_contacts_for_client(test_client, test_db):
    """Test fetching contacts for a client"""
    # Get a client with contacts
    client = test_db.execute(
        """
        SELECT c.client_id 
        FROM clients c 
        JOIN contacts co ON c.client_id = co.client_id 
        WHERE co.valid_to IS NULL 
        LIMIT 1
        """
    ).fetchone()
    
    if client:
        client_id = client["client_id"]
        response = test_client.get(f"/api/contacts/client/{client_id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        
        if len(response.json()) > 0:
            # Check that the contact has expected fields
            contact = response.json()[0]
            assert "contact_id" in contact
            assert "client_id" in contact
            assert "contact_type" in contact