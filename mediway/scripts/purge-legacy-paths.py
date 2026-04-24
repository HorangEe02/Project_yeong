#!/usr/bin/env python3
"""
T1-1 / T1-2 후속 cleanup — 레거시 `/audit_logs` + `/visit_plans` 완전 purge.

⚠️ 실행 전제 조건 (모두 충족해야 함):

  1. LIVE hosting 번들이 prod parity 에 도달 + 전체 재배포 완료된 상태
     (Phase B-3 item 10 `/h/:slug/*` nested routing + HospitalShell 이식 이후)
  2. 새 프런트엔드가 `audit_logs_v2/{hid}` · `hospitals/{hid}/visit_plans/{uid}`
     에만 read/write 하도록 업그레이드 된 것을 LIVE 브라우저 검증
  3. `/audit_logs` 와 `/visit_plans` 로의 RTDB traffic (write + read) 이
     관측상 0 건 유지 — Firebase console · Usage 탭에서 최소 24시간 확인
  4. 백업 파일 (`/audit_logs_backup_*`, `/visit_plans_backup_*`) 이 여전히
     RTDB 에 존재. rollback 경로 확보

위 조건 충족 전 실행 금지. 조건 체크 후 --confirm 플래그 사용.

사용:
    python3 scripts/purge-legacy-paths.py --dry-run
    python3 scripts/purge-legacy-paths.py --apply --confirm
"""
import argparse
import json
import subprocess
import sys
import urllib.request

DB = 'https://mediway-demo-default-rtdb.firebaseio.com'
LEGACY_PATHS = ['/audit_logs', '/visit_plans']


def token() -> str:
    return subprocess.run(
        ['gcloud', 'auth', 'print-access-token'],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def api(method: str, path: str, body=None):
    url = f'{DB}{path}.json?access_token={token()}'
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'} if body is not None else {}
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b'null')


def summary() -> dict:
    result = {}
    for p in LEGACY_PATHS:
        data = api('GET', f'{p}?shallow=true') or {}
        result[p] = len(data) if isinstance(data, dict) else 0
    root = api('GET', '/') or {}
    backups = {k: '<present>' for k in root if k.startswith('audit_logs_backup_') or k.startswith('visit_plans_backup_')}
    return {'legacy_counts': result, 'backups_detected': backups}


def dry_run() -> None:
    s = summary()
    print('=== 현 상태 ===')
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print('\n=== 실행 대상 ===')
    for p, c in s['legacy_counts'].items():
        print(f'  purge {p}: {c} entries')
    print('\n백업 보존:', list(s['backups_detected'].keys()))
    print('\n실행하려면 --apply --confirm 함께 사용.')


def apply_purge() -> None:
    s = summary()
    if not any(s['backups_detected'].keys()):
        print('ABORT: 백업 entries 미확인 — rollback 경로 없음', file=sys.stderr)
        sys.exit(2)
    print('=== purge 시작 ===')
    for p, c in s['legacy_counts'].items():
        if c == 0:
            print(f'  {p}: 이미 비어있음, skip')
            continue
        api('DELETE', p)
        print(f'  ✓ {p} deleted ({c} entries)')
    print('\n=== verify ===')
    for p in LEGACY_PATHS:
        after = api('GET', f'{p}?shallow=true')
        print(f'  {p} after: {after if after else "empty"}')
    print('\n백업은 그대로 보존 (rollback 경로).')


def main() -> None:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry-run', action='store_true')
    g.add_argument('--apply', action='store_true')
    p.add_argument('--confirm', action='store_true',
                   help='required with --apply, signals operator has verified prerequisites')
    args = p.parse_args()
    if args.dry_run:
        dry_run()
    elif args.apply:
        if not args.confirm:
            print('ERROR: --apply requires --confirm (문서의 전제 조건 모두 확인했음을 확약)',
                  file=sys.stderr)
            sys.exit(1)
        apply_purge()


if __name__ == '__main__':
    main()
