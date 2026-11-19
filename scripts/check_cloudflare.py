"""Check credentials and run one small inference without printing secrets."""
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def settings():
    values = {}
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main():
    values = settings()
    account = values.get('CLOUDFLARE_ACCOUNT_ID', '')
    token = values.get('CLOUDFLARE_API_TOKEN', '')
    model = values.get('CLOUDFLARE_AI_MODEL', '')
    if not account or not token or not model:
        print('Missing Cloudflare settings in .env')
        return 1
    body = json.dumps({'messages': [{'role': 'user', 'content': 'Reply with only the word OK.'}], 'max_tokens': 12, 'temperature': 0}).encode()
    request = Request(f'https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}', data=body,
                      headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=45) as response:
            data = json.load(response)
        print(json.dumps({'success': data.get('success'), 'model': model,
                          'response': data.get('result', {}).get('response', '')[:80]}, ensure_ascii=False))
        return 0 if data.get('success') else 1
    except HTTPError as exc:
        try:
            data = json.loads(exc.read())
            codes = [e.get('code') for e in data.get('errors', [])]
        except Exception:
            codes = []
        print(json.dumps({'http_status': exc.code, 'error_codes': codes}))
        return 1
    except (URLError, OSError) as exc:
        print('Network connection failed: ' + type(exc).__name__)
        return 2


if __name__ == '__main__':
    sys.exit(main())
