import pytest
from playwright.sync_api import Page, expect
import threading
from app import create_app
import time

# Custom fixture to run a thread-based live server because LiveServer fixture fails on Windows due to PicklingError
@pytest.fixture(scope="session")
def local_server():
    app = create_app()
    app.config['TESTING'] = True
    # Run server in a thread
    server_thread = threading.Thread(target=lambda: app.run(port=5001, debug=False, use_reloader=False))
    server_thread.daemon = True
    server_thread.start()
    # Give it a second to start
    time.sleep(1)
    return "http://localhost:5001"

def test_index_has_title(page: Page, local_server):
    # Navigate to the local server
    page.goto(local_server)
    # Expect the title to contain "NFL Fantasy Football"
    expect(page).to_have_title("NFL Fantasy Football")

def test_navigation_to_login(page: Page, local_server):
    page.goto(local_server)
    # Find the login link and click it
    page.click("text=Login")
    # Expect URL to be redirected to login
    expect(page).to_have_url(f"{local_server}/login")
    # Check for login form or heading
    expect(page.get_by_role("heading", name="Login")).to_be_visible()
