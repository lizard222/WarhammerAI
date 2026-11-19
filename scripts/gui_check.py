"""Capture actual Tkinter windows while exercising the standalone HTTP client."""
import json
import ctypes
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop'))
from app import StoreApp
from PIL import ImageGrab


def main():
    app = StoreApp('http://127.0.0.1:8000')
    app.geometry('1200x820+80+60')
    app.update()

    def settle(timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            app.update()
            if app.pending == 0:
                app.update()
                return
            time.sleep(0.08)
        raise RuntimeError('GUI request did not complete')

    def capture(name):
        app.update()
        hwnd = ctypes.windll.user32.GetAncestor(app.winfo_id(), 2)
        # Capture this HWND directly: unrelated foreground windows never enter the report.
        ImageGrab.grab(window=hwnd).save(ROOT / 'docs/screenshots' / name)

    settle()
    assert len(app.product_tree.get_children()) == 15
    capture('desktop_catalog.png')
    user = app.client.login('demo', 'WarhammerDemo2026!')
    app.logged_in(user)
    settle()
    app.tabs.select(app.ai_tab)
    app.ask_ai()
    settle(60)
    assert app.recommendations
    capture('desktop_recommendations.png')
    first = next(iter(app.recommendations))
    app.recommend_tree.selection_set(str(first))
    app.add_recommendation()
    settle()
    app.tabs.select(app.cart_tab)
    settle()
    assert app.cart_items
    capture('desktop_cart.png')
    result = app.client.request('orders/', 'POST', {})
    assert result['items']
    app.tabs.select(app.orders_tab)
    app.load_orders()
    settle()
    assert app.orders_tree.get_children()
    capture('desktop_orders.png')
    evidence = {'verified_at': datetime.now(timezone.utc).isoformat(), 'passed': True,
                'checks': ['15 products in Tkinter', 'standalone token login', 'real AI recommendations',
                           'add recommendation to cart', 'checkout through standalone HTTP client', 'order history in GUI']}
    (ROOT / 'docs/gui_validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    app.close()
    print('GUI CHECK PASSED:', len(evidence['checks']), 'checks')


if __name__ == '__main__':
    main()
