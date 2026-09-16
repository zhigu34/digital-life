"""Exercise the actual shell entry point with an isolated Docker process double."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('deploy', '.env.example', 'docker-compose.yml', '.gitignore'):
            if (ROOT / name).exists():
                shutil.copy(ROOT / name, self.root / name)
        (self.root / 'backend').mkdir()
        (self.root / 'backend' / 'sample.py').write_text('version = 1\n')
        (self.root / 'frontend').mkdir()
        (self.root / 'frontend' / 'sample.ts').write_text('const version = 1\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        docker = self.bin / 'docker'
        docker.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_LOG"
case "$*" in
  *" info "*|"info "*) echo x86_64;;
  *" ps -q backend"*) echo fake-backend;;
  *" ps -q frontend"*) echo fake-frontend;;
  *"image inspect"*) [ -f "$FAKE_IMAGES_MISSING" ] && exit 1; echo amd64;;
  *"pull"*) rm -f "$FAKE_IMAGES_MISSING";;
  *"inspect "*"fake-backend"*) if [ -f "$FAKE_STOP_FILE" ]; then echo exited; else echo healthy; fi;;
  *"inspect "*) echo healthy;;
  *" up -d --no-build") rm -f "$FAKE_STOP_FILE";;
  *"build"*) [ "${FAIL_BUILD:-0}" = 0 ] || exit 9;;
  *"run "*"migrate"*) [ "${FAIL_MIGRATE:-0}" = 0 ] || exit 10;;
  *"run "*"pending-migration"*) [ "${FAKE_MIGRATION_PENDING:-1}" = 0 ] && exit 0; exit 1;;
  *" exec "*"urllib"*) if [ -n "${FAKE_HEALTH_TRANSIENT:-}" ]; then n="$(cat "$FAKE_HEALTH_COUNT" 2>/dev/null || echo 0)"; echo "$((n + 1))" > "$FAKE_HEALTH_COUNT"; [ "$n" -ge "$FAKE_HEALTH_TRANSIENT" ] || exit 11; fi; [ "${FAIL_HEALTH:-0}" = 0 ] || exit 11;;
esac
exit 0
''')
        docker.chmod(0o755)
        self.env = {**os.environ, 'PATH': f'{self.bin}:{os.environ["PATH"]}',
                    'FAKE_LOG': str(self.root / 'docker.log'),
                    'FAKE_STOP_FILE': str(self.root / 'stopped-backend'),
                    'FAKE_HEALTH_COUNT': str(self.root / 'health-count')}
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                        'commit', '-qm', 'fixture'], cwd=self.root, check=True)

    def run_deploy(self, *args, **env):
        return subprocess.run(['bash', 'deploy', *args], cwd=self.root,
                              env={**self.env, **env}, text=True, capture_output=True)

    def log(self):
        p = self.root / 'docker.log'
        return p.read_text() if p.exists() else ''

    def test_check_only_does_not_write_runtime_state(self):
        result = self.run_deploy('--check-only')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ('.env', 'logs', 'data', 'backups'):
            self.assertFalse((self.root / name).exists(), name)
        self.assertNotIn(' up ', self.log())
        self.assertNotIn(' build ', self.log())

    def test_failed_build_does_not_stop_running_services_or_record_success(self):
        result = self.run_deploy(FAIL_BUILD='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('build backend frontend', self.log())
        self.assertNotIn(' stop ', self.log())
        self.assertFalse((self.root / 'logs' / 'deploy-state').exists())

    def test_success_records_state_and_unchanged_source_skips_build(self):
        first = self.run_deploy()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertTrue((self.root / 'logs' / 'deploy-state').exists())
        (self.root / 'docker.log').write_text('')
        second = self.run_deploy()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotIn(' build ', self.log())

    def test_frontend_change_only_rebuilds_frontend(self):
        self.assertEqual(self.run_deploy().returncode, 0)
        (self.root / 'docker.log').write_text('')
        (self.root / 'frontend' / 'sample.ts').write_text('const version = 2\n')
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('build frontend', self.log())
        self.assertNotIn(' stop backend', self.log())
        self.assertNotIn('build backend', self.log())

    def test_frontend_update_recovers_stopped_unchanged_backend(self):
        self.assertEqual(self.run_deploy().returncode, 0)
        (self.root / 'stopped-backend').touch()
        (self.root / 'frontend' / 'sample.ts').write_text('const version = 3\n')
        result = self.run_deploy(DIGITAL_LIFE_HEALTH_ATTEMPTS='1')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / 'stopped-backend').exists())

    def test_failed_migration_does_not_record_success(self):
        result = self.run_deploy(FAIL_MIGRATE='1')
        self.assertIn('app.cli migrate', self.log())
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'logs' / 'deploy-state').exists())

    def test_failed_public_health_does_not_record_success(self):
        result = self.run_deploy(FAIL_HEALTH='1', DIGITAL_LIFE_HEALTH_ATTEMPTS='1')
        self.assertIn('urllib', self.log())
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'logs' / 'deploy-state').exists())

    def test_missing_base_image_is_pulled_before_build(self):
        images_missing = self.root / 'images-missing'
        images_missing.touch()
        result = self.run_deploy(FAKE_IMAGES_MISSING=str(images_missing))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('pull', self.log())
        self.assertFalse(images_missing.exists())

    def test_occupied_port_is_rejected_before_deployment(self):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.listen(1)
        self.addCleanup(sock.close)
        result = self.run_deploy('--check-only', DIGITAL_LIFE_WEB_PORT=str(port))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(port), result.stderr)
        self.assertIn('已被其他进程占用', result.stderr)

    def test_up_to_date_database_skips_stop_backup_and_migrate(self):
        result = self.run_deploy(FAKE_MIGRATION_PENDING='0')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = self.log()
        self.assertNotIn(' stop ', log)
        self.assertNotIn(' backup ', log)
        self.assertNotIn(' migrate', log)
        self.assertIn('pending-migration', log)
        self.assertIn('跳过停服备份与迁移', result.stdout)
        self.assertTrue((self.root / 'logs' / 'deploy-state').exists())

    def test_pending_database_still_stops_and_backs_up(self):
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'digital-life.db').write_text('existing db')
        result = self.run_deploy(FAKE_MIGRATION_PENDING='1')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = self.log()
        self.assertIn(' stop backend', log)
        self.assertIn(' backup --output', log)
        self.assertIn('app.cli migrate', log)

    def test_success_prunes_old_predeploy_backups_but_keeps_manual(self):
        backups = self.root / 'backups'
        backups.mkdir()
        for index in range(12):
            (backups / f'pre-deploy-20260916T000{index:02d}Z-{index}.db').write_text('x')
        manual = backups / 'manual-20260101T000000Z-1.db'
        manual.write_text('keep me')
        result = self.run_deploy(FAKE_MIGRATION_PENDING='0')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        remaining_pre = sorted(p.name for p in backups.glob('pre-deploy-*.db'))
        self.assertEqual(len(remaining_pre), 10)
        self.assertTrue(manual.exists())

    def test_transient_web_gateway_errors_retry_to_success(self):
        result = self.run_deploy(FAKE_HEALTH_TRANSIENT='2')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Web 入口暂未就绪', result.stdout)
        self.assertTrue((self.root / 'logs' / 'deploy-state').exists())

    def test_web_gateway_check_bypasses_proxy(self):
        # The backend container may carry HTTP(S)_PROXY for outbound metadata
        # lookups; the in-network gateway check must bypass them, otherwise the
        # proxy intercepts the request and the deploy fails on every retry.
        result = self.run_deploy(FAKE_MIGRATION_PENDING='0')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('-e HTTP_PROXY= -e HTTPS_PROXY= -e ALL_PROXY=', self.log())

    def test_previous_deploy_log_is_preserved(self):
        first = self.run_deploy(FAKE_MIGRATION_PENDING='0')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        (self.root / 'logs' / 'deploy.log').write_text('previous run evidence\n')
        second = self.run_deploy(FAKE_MIGRATION_PENDING='0')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual((self.root / 'logs' / 'deploy.log.1').read_text(),
                         'previous run evidence\n')

    def test_port_check_can_be_skipped(self):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.listen(1)
        self.addCleanup(sock.close)
        result = self.run_deploy('--check-only', DIGITAL_LIFE_WEB_PORT=str(port),
                                 DEPLOY_SKIP_PORT_CHECK='1')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()


class ComposeEnvironmentTest(unittest.TestCase):
    """Every .env knob the app reads at runtime must reach the backend container."""

    def test_backend_container_receives_all_runtime_env_vars(self):
        compose = Path(__file__).resolve().parents[2] / 'docker-compose.yml'
        text = compose.read_text(encoding='utf-8')
        backend_section = text.split('  frontend:')[0]
        for var in (
            'DIGITAL_LIFE_DATA_DIR',
            'DIGITAL_LIFE_SECURE_COOKIE',
            'DIGITAL_LIFE_TRUSTED_ORIGINS',
            'DIGITAL_LIFE_DISABLE_METADATA',
            'DIGITAL_LIFE_TMDB_API_KEY',
            'HTTP_PROXY',
            'HTTPS_PROXY',
            'ALL_PROXY',
            'NO_PROXY',
            'TZ',
        ):
            self.assertIn(var, backend_section, f'{var} missing from backend environment')
