# backend/tests/conftest.py
import pytest
import sqlite3
import os
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db_connection

@pytest.fixture
def test_client():
    """Create a test client using the test database"""
    return TestClient(app)

@pytest.fixture
def test_db():
    """Get a connection to the test database"""
    conn = get_db_connection(test_mode=True)
    yield conn
    conn.close()