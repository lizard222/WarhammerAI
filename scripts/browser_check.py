"""Exercise the actual browser UI and save report screenshots."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    screenshots = ROOT / 'docs/screenshots'
    screenshots.mkdir(exist_ok=True, parents=True)
    errors = []
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:8000/', wait_until='networkidle')
        page.locator('.product').first.wait_for()
        assert page.locator('.product').count() == 15
        page.locator('.product-image img').evaluate_all("images=>images.forEach(i=>i.loading='eager')")
        page.wait_for_function("[...document.querySelectorAll('.product-image img')].every(i=>i.complete && i.naturalWidth>0)")
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(screenshots / 'web_catalog.png'))
        checks.append('15 product cards and local images')
        missing = page.locator('.product-image img').evaluate_all('(images)=>images.filter(i=>!i.complete || i.naturalWidth===0).length')
        assert missing == 0, 'Missing product images'
        page.select_option('select[name=type]', 'PAINT')
        page.get_by_role('button', name='Применить', exact=True).click()
        page.wait_for_function("document.querySelectorAll('.product').length===3")
        checks.append('category filter via REST API')
        page.get_by_role('button', name='Сбросить', exact=True).click()
        page.wait_for_function("document.querySelectorAll('.product').length===15")
        page.locator('#auth-button').click()
        page.locator('#login-form [name=username]').fill('demo')
        page.locator('#login-form [name=password]').fill('WarhammerDemo2026!')
        page.get_by_role('button', name='Войти в магазин', exact=True).click()
        page.wait_for_function("document.querySelector('#auth-button').textContent.includes('demo')")
        checks.append('login through browser form')
        page.locator('[data-nav=advisor]').click()
        page.locator('[name=preferences]').fill('Я новичок. Хочу начать собирать космодесант и попробовать покраску.')
        page.locator('[name=budget]').fill('6000')
        page.locator('#advisor-form [type=submit]').click()
        page.locator('.recommend-card').first.wait_for(timeout=60000)
        assert 1 <= page.locator('.recommend-card').count() <= 3
        page.screenshot(path=str(screenshots / 'web_recommendations.png'), full_page=True)
        checks.append('real AI recommendations shown in the browser')
        page.locator('.recommend-card [data-add]').first.click()
        page.wait_for_function("Number(document.querySelector('#cart-count').textContent)>0")
        page.locator('[data-nav=cart]').click()
        page.locator('.cart-item').first.wait_for()
        page.screenshot(path=str(screenshots / 'web_cart.png'))
        checks.append('add recommendation to cart')
        page.locator('#checkout').click()
        page.locator('.order').first.wait_for()
        page.screenshot(path=str(screenshots / 'web_orders.png'))
        checks.append('checkout and persistent order history')
        mobile = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=1)
        mobile.goto('http://127.0.0.1:8000/', wait_until='networkidle')
        mobile.locator('.product').first.wait_for()
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile horizontal overflow'
        mobile.screenshot(path=str(screenshots / 'web_mobile.png'), full_page=False)
        checks.append('390px responsive layout without horizontal overflow')
        assert not errors, errors
        browser.close()
    evidence = {'verified_at': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'javascript_errors': errors, 'passed': True}
    (ROOT / 'docs/browser_validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BROWSER CHECK PASSED:', len(checks), 'checks')


if __name__ == '__main__':
    main()
