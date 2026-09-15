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
    items = request('/api/maintenance')
    maintenance = next(item for item in items if item['title'] == 'CI filter sentinel')
    assert maintenance['last_completed'] == '2000-03-31'
    assert maintenance['next_due'] == '2000-04-30'
    history = request(f"/api/maintenance/{maintenance['id']}/history")
    assert len(history) == 2
    assert history[0]['cost_cents'] == 12950
    print('Account, task, recurring maintenance and completion history survived container recreation.')
else:
    task = request('/api/tasks', {'title': 'CI persistence sentinel'}, login['csrf_token'])
    assert task['title'] == 'CI persistence sentinel'
    maintenance = request('/api/maintenance', {
        'title': 'CI filter sentinel', 'last_completed': '2000-01-31',
        'period_value': 1, 'period_unit': 'months', 'remind_days': 14,
    }, login['csrf_token'])
    assert maintenance['next_due'] == '2000-02-29'
    completed = request(f"/api/maintenance/{maintenance['id']}/complete", {
        'completed_on': '2000-03-31', 'cost_cents': 12950, 'notes': 'CI replacement',
    }, login['csrf_token'])
    assert completed['next_due'] == '2000-04-30'
    exported = request('/api/export')
    assert any(t['id'] == task['id'] for t in exported['tasks'])
    assert any(item['id'] == maintenance['id'] for item in exported['maintenance'])
    assert len([row for row in exported['maintenance_logs'] if row['maintenance_id'] == maintenance['id']]) == 2
    container = subprocess.check_output(['docker', 'compose', 'ps', '-q', 'backend'], text=True).strip()
    details = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    assert not (details['HostConfig'].get('PortBindings') or {}).get('8000/tcp')
    print('Authenticated CRUD/export and internal-only backend verified.')
