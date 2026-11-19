"""Deploy the module Worker through HTTPS; Node.js and Wrangler are not required."""
import json
import secrets
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from check_cloudflare import settings, ROOT


def main():
    values = settings()
    token = values['CLOUDFLARE_API_TOKEN']
    account = values['CLOUDFLARE_ACCOUNT_ID']
    name = values.get('CLOUDFLARE_WORKER_NAME', 'warhammer-ai-recommendations')
    model = values.get('CLOUDFLARE_AI_MODEL', '@cf/meta/llama-3.3-70b-instruct-fp8-fast')
    service_key = values.get('RECOMMENDATIONS_API_KEY') or secrets.token_urlsafe(36)
    # Persist before deployment so an interrupted upload never loses the shared secret.
    env_path = ROOT / '.env'
    lines = env_path.read_text(encoding='utf-8-sig').splitlines()
    if not values.get('RECOMMENDATIONS_API_KEY'):
        lines = [line for line in lines if not line.startswith('RECOMMENDATIONS_API_KEY=')]
        lines.append('RECOMMENDATIONS_API_KEY=' + service_key)
        env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def api(path, method='GET', payload=None, content_type='application/json'):
        body = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        request = Request(f'https://api.cloudflare.com/client/v4/accounts/{account}/workers/{path}', data=body,
                          method=method, headers={'Authorization': 'Bearer ' + token, 'Content-Type': content_type})
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
        except HTTPError as exc:
            error = json.loads(exc.read())
            codes = [e.get('code') for e in error.get('errors', [])]
            raise RuntimeError(f'Cloudflare HTTP {exc.code}; error codes: {codes}') from None
        if not result.get('success'):
            raise RuntimeError('Cloudflare rejected request: ' + str([e.get('code') for e in result.get('errors', [])]))
        return result.get('result', {})

    subdomain_result = api('subdomain')
    subdomain = subdomain_result.get('subdomain')
    if not subdomain:
        subdomain = 'warhammer-cw-' + account[:8]
        api('subdomain', 'PUT', {'subdomain': subdomain})
    metadata = {'main_module': 'worker.mjs', 'compatibility_date': '2026-11-19',
                'bindings': [{'name': 'AI', 'type': 'ai'}, {'name': 'MODEL', 'type': 'plain_text', 'text': model},
                             {'name': 'SERVICE_API_KEY', 'type': 'secret_text', 'text': service_key}]}
    boundary = '----WarhammerUpload' + secrets.token_hex(12)
    parts = []
    for part_name, filename, mime, content in [
        ('metadata', 'metadata.json', 'application/json', json.dumps(metadata).encode()),
        ('worker.mjs', 'worker.mjs', 'application/javascript+module', (ROOT / 'cloud_function/worker.mjs').read_bytes())]:
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{part_name}"; filename="{filename}"\r\n'
                      f'Content-Type: {mime}\r\n\r\n').encode() + content + b'\r\n')
    body = b''.join(parts) + f'--{boundary}--\r\n'.encode()
    result = api('scripts/' + name, 'PUT', body, 'multipart/form-data; boundary=' + boundary)
    api('scripts/' + name + '/subdomain', 'POST', {'enabled': True, 'previews_enabled': False})
    url = f'https://{name}.{subdomain}.workers.dev'
    lines = env_path.read_text(encoding='utf-8').splitlines()
    lines = [line for line in lines if not line.startswith('RECOMMENDATIONS_URL=')]
    lines.append('RECOMMENDATIONS_URL=' + url)
    env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    evidence = {'url': url, 'model': model, 'worker_name': name, 'deployed': True,
                'deployment_id': result.get('deployment_id'), 'platform': 'Cloudflare Workers + Workers AI'}
    (ROOT / 'docs/deployment.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Worker deployed: ' + url)
    print('Django settings saved to .env. Secrets were not printed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc))
        sys.exit(1)
