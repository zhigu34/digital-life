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


BOUNDARY = 'digital-life-ci-boundary'


def multipart_put(path, filename, content_type, body, csrf):
    """Upload one file part and return (status, body) instead of raising on 4xx."""
    payload = b''.join((
        f'--{BOUNDARY}\r\n'.encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f'Content-Type: {content_type}\r\n\r\n'.encode(),
        body,
        f'\r\n--{BOUNDARY}--\r\n'.encode(),
    ))
    req = urllib.request.Request(base + path, data=payload, method='PUT', headers={
        'Content-Type': f'multipart/form-data; boundary={BOUNDARY}',
        'Origin': base,
        'X-CSRF-Token': csrf,
    })
    try:
        with http.open(req, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


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
    stats = request('/api/stats?end_month=2000-04')
    march = next(month for month in stats['months'] if month['month'] == '2000-03')
    assert march['maintenance_cost'] == {'CNY': 12950}, march
    print('Account, task, maintenance history and stats survived container recreation.')
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
    stats = request('/api/stats?end_month=2000-04')
    assert len(stats['months']) == 12
    march = next(month for month in stats['months'] if month['month'] == '2000-03')
    assert march['maintenance_cost'] == {'CNY': 12950}, march
    assert all(month['expense_due'] == {} for month in stats['months'])
    assert stats['shows']['episodes_watched'] >= 0
    exported = request('/api/export')
    assert any(t['id'] == task['id'] for t in exported['tasks'])
    assert any(item['id'] == maintenance['id'] for item in exported['maintenance'])
    assert len([row for row in exported['maintenance_logs'] if row['maintenance_id'] == maintenance['id']]) == 2

    # Covers are uploaded from a phone, so the body size the proxy allows is part
    # of the feature: a 3 MB photo has to survive the public entry, and the app's
    # own 5 MB cap must be what rejects more — with a JSON error, not an nginx 413
    # page the UI can only report as a generic failure.
    show = request('/api/shows', {'title': 'CI poster size sentinel'}, login['csrf_token'])
    photo = b'\x89PNG\r\n\x1a\n' + bytes(3_000_000)
    status, body = multipart_put(f"/api/shows/{show['id']}/poster", 'photo.png',
                                 'image/png', photo, login['csrf_token'])
    assert status == 200, (status, body[:200])
    with http.open(base + f"/api/shows/{show['id']}/poster", timeout=30) as response:
        assert response.read() == photo, 'cover came back truncated through the proxy'
    status, body = multipart_put(f"/api/shows/{show['id']}/poster", 'huge.png',
                                 'image/png', b'\x89PNG\r\n\x1a\n' + bytes(5_000_001),
                                 login['csrf_token'])
    assert status == 413, (status, body[:200])
    try:
        detail = json.loads(body)['detail']
    except (ValueError, KeyError):
        raise AssertionError(f'expected the backend JSON 413, got {status} {body[:200]}') from None
    assert '5 MB' in detail, detail

    container = subprocess.check_output(['docker', 'compose', 'ps', '-q', 'backend'], text=True).strip()
    details = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    assert not (details['HostConfig'].get('PortBindings') or {}).get('8000/tcp')
    print('Authenticated CRUD/export and internal-only backend verified.')
