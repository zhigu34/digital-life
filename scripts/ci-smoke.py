"""Real HTTP and Docker integration checks against an operator-created CI account."""
import http.cookiejar
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

base = os.environ.get('E2E_BASE_URL', 'http://127.0.0.1:8090')
jar = http.cookiejar.CookieJar()
http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path, data=None, csrf=None):
    headers = {'Content-Type': 'application/json', 'Origin': base}
    if csrf:
        headers['X-CSRF-Token'] = csrf
    req = urllib.request.Request(base + path, headers=headers,
                                 data=json.dumps(data).encode() if data is not None else None)
    with http.open(req, timeout=10) as response:
        return json.load(response)


for public_path in ('/', '/health'):
    with urllib.request.urlopen(base + public_path, timeout=10) as response:
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('X-Frame-Options') == 'DENY'
        assert response.headers.get('Referrer-Policy') == 'same-origin'
        if public_path == '/health':
            assert response.headers.get('Cache-Control') == 'no-store'

login = request('/api/auth/login', {'username': os.environ['E2E_ADMIN_USERNAME'],
                                    'password': os.environ['E2E_ADMIN_PASSWORD']})
if '--verify-persistence' in sys.argv:
    tasks = request('/api/tasks')
    assert any(task['title'] == 'CI persistence sentinel' for task in tasks), tasks
    print('Existing account and task survived container recreation.')
else:
    task = request('/api/tasks', {'title': 'CI persistence sentinel'}, login['csrf_token'])
    assert task['title'] == 'CI persistence sentinel'
    exported = request('/api/export')
    assert any(t['id'] == task['id'] for t in exported['tasks'])
    container = subprocess.check_output(['docker', 'compose', 'ps', '-q', 'backend'], text=True).strip()
    details = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    assert not (details['HostConfig'].get('PortBindings') or {}).get('8000/tcp')
    print('Authenticated CRUD/export and internal-only backend verified.')
