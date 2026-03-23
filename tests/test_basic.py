import pytest

def test_index_page(client):
    """Test that the index page loads successfully."""
    response = client.get('/')
    assert response.status_code == 200

def test_login_page(client):
    """Test that the login page loads successfully."""
    response = client.get('/login')
    assert response.status_code == 200

def test_register_page(client):
    """Test that the register page loads successfully."""
    response = client.get('/register')
    assert response.status_code == 200
