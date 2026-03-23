import pytest
from app import create_app
from database import Database
import mongomock

@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    
    # Mock the database for tests
    with mongomock.patch(servers=(('localhost', 27017),)):
        yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
