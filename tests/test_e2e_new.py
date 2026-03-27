import pytest
from playwright.sync_api import Page, expect
import threading
from app import create_app
import time


@pytest.fixture(scope="session")
def local_server():
    app = create_app()
    app.config['TESTING'] = True
    server_thread = threading.Thread(
        target=lambda: app.run(port=5002, debug=False, use_reloader=False)
    )
    server_thread.daemon = True
    server_thread.start()
    time.sleep(1)
    return "http://localhost:5002"


# ─── Theme Toggle ────────────────────────────────────────────────────────────

def test_theme_toggle_cycles(page: Page, local_server):
    page.goto(local_server)
    toggle = page.locator('#themeToggle')
    # Default is light
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == 'light'
    # Click to dark
    toggle.click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == 'dark'
    # Click to home
    toggle.click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == 'home'
    # Click to away
    toggle.click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == 'away'
    # Click back to light
    toggle.click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == 'light'


def test_theme_persists_across_navigation(page: Page, local_server):
    page.goto(local_server)
    page.locator('#themeToggle').click()  # switch to dark
    page.goto(f"{local_server}/login")
    theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert theme == 'dark'


# ─── Navigation ──────────────────────────────────────────────────────────────

def test_nfl_nav_links(page: Page, local_server):
    page.goto(f"{local_server}/nfl/home")
    expect(page.locator('.sub-nav')).to_be_visible()
    expect(page.locator('.sub-nav a.active')).to_be_visible()


def test_vertical_nav_visible_on_nfl(page: Page, local_server):
    page.goto(f"{local_server}/nfl/home")
    expect(page.locator('.vertical-nav')).to_be_visible()


def test_vertical_nav_tooltip_on_hover(page: Page, local_server):
    page.goto(f"{local_server}/nfl/home")
    first_link = page.locator('.vertical-nav a').first
    label = first_link.get_attribute('data-label')
    assert label is not None and len(label) > 0


# ─── Registration & Login ────────────────────────────────────────────────────

def test_register_and_login_flow(page: Page, local_server):
    import uuid
    username = f"e2e_{uuid.uuid4().hex[:6]}"
    # Register
    page.goto(f"{local_server}/register")
    page.fill('input[name="username"]', username)
    page.fill('input[name="email"]', f"{username}@test.com")
    page.fill('input[name="password"]', "testpass123")
    page.click('button[type="submit"]')
    expect(page.locator('.flash.success')).to_be_visible()
    # Login
    page.goto(f"{local_server}/login")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', "testpass123")
    page.click('button[type="submit"]')
    expect(page).to_have_url(f"{local_server}/leagues/my")


def test_login_invalid_credentials(page: Page, local_server):
    page.goto(f"{local_server}/login")
    page.fill('input[name="username"]', "nobody")
    page.fill('input[name="password"]', "wrongpass")
    page.click('button[type="submit"]')
    expect(page.locator('.flash.error')).to_be_visible()


# ─── Flatpickr ───────────────────────────────────────────────────────────────

def test_flatpickr_not_initialized_on_non_date_inputs(page: Page, local_server):
    page.goto(f"{local_server}/login")
    # Login input should NOT have flatpickr class
    username_input = page.locator('input[name="username"]')
    classes = username_input.get_attribute('class') or ''
    assert 'flatpickr' not in classes
