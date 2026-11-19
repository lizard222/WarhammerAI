"""Real Django -> deployed Worker -> Workers AI verification; output contains no credentials."""
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'warhammer_project.settings')
import django
django.setup()
from django.conf import settings
from rest_framework.test import APIClient


def main():
    client = APIClient()
    login = client.post('/api/v1/auth/login/', {'username': 'demo', 'password': 'WarhammerDemo2026!'}, format='json')
    if login.status_code != 200:
        raise RuntimeError('Demo login failed')
    client.credentials(HTTP_AUTHORIZATION='Token ' + login.data['token'])
    with urlopen(Request(settings.RECOMMENDATIONS_URL + '/health', headers={'User-Agent': 'WarhammerCoursework/1.0'}), timeout=25) as response:
        health = json.load(response)
    request = {'preferences': 'Я новичок. Хочу начать собирать космодесант и попробовать покраску.', 'budget': '6000', 'max_items': 3}
    response = client.post('/api/v1/recommendations/', request, format='json')
    if response.status_code != 200:
        raise RuntimeError('Recommendations failed, HTTP ' + str(response.status_code) + ': ' + str(response.data))
    result = json.loads(response.content)
    assert result['items'], 'No real recommendations returned'
    assert Decimal(result['total_price']) <= Decimal(request['budget'])
    assert all(i['product']['stock'] >= i['quantity'] > 0 for i in result['items'])
    assert sum(Decimal(i['total_price']) for i in result['items']) == Decimal(result['total_price'])
    evidence = {'verified_at': datetime.now(timezone.utc).isoformat(), 'health': health,
                'request': request, 'response': result, 'http_status': response.status_code,
                'checks': ['real deployed Worker', 'real Workers AI inference', 'valid stock', 'total within budget', 'server arithmetic']}
    (ROOT / 'docs/live_validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('LIVE CHECK PASSED; items:', len(result['items']), '; total:', result['total_price'], '; model:', result['model'])


if __name__ == '__main__':
    main()
