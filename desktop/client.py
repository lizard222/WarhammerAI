"""Standalone HTTP client. It does not import Django or open the database."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def error_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ' '.join(error_text(v) for v in value)
    if isinstance(value, dict):
        return ' '.join(error_text(v) for v in value.values())
    return str(value)


class StoreClient:
    def __init__(self, base_url='http://127.0.0.1:8000'):
        self.base_url = base_url.rstrip('/')
        self.token = ''
        self.user = None

    def request(self, path, method='GET', data=None):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Token ' + self.token
        request = Request(self.base_url + '/api/v1/' + path, method=method, headers=headers,
                          data=json.dumps(data).encode('utf-8') if data is not None else None)
        try:
            with urlopen(request, timeout=55) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as exc:
            try:
                message = error_text(json.loads(exc.read()))
            except Exception:
                message = 'Ошибка сервера: ' + str(exc.code)
            raise RuntimeError(message) from None
        except (URLError, OSError):
            raise RuntimeError('Сервер недоступен или превышено время ожидания. Проверьте адрес и подключение.') from None

    def login(self, username, password):
        result = self.request('auth/login/', 'POST', {'username': username, 'password': password})
        self.token, self.user = result['token'], result['user']
        return self.user

    def logout(self):
        self.request('auth/logout/', 'POST', {})
        self.token, self.user = '', None
