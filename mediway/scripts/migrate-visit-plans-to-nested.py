#!/usr/bin/env python3
"""
T1-2a — legacy `/visit_plans/{uid}` 을 `/hospitals/{hospitalId}/visit_plans/{uid}` 로 이관.

bucket 분류:
    1) `/users/{uid}/primaryHospitalId` 존재 → 그 값
    2) `/users/{uid}/hospitalId` 존재 → 그 값
    3) 그 외 → `unknown` bucket (수동 라벨링 필요)

사용:
    python3 scripts/migrate-visit-plans-to-nested.py --dry-run
    python3 scripts/migrate-visit-plans-to-nested.py --apply
    python3 scripts/migrate-visit-plans-to-nested.py --rollback TIMESTAMP

후속:
    T1-2c 에서 legacy /visit_plans write 차단 + rules tighten.
    legacy entries 는 platformAdmin read-only 로 보존 (audit 과 동일 정책).
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request

DB = 'https://mediway-demo-default-rtdb.firebaseio.com'


def token() -> str:
    return subprocess.run(
        ['gcloud', 'auth', 'print-access-token'],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def api(method: str, path: str, body=None):
    p = path if path.startswith('/') else f'/{path}'
    url = f'{DB}{p}.json?access_token={token()}'
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'} if body is not None else {}
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b'null')


def resolve_bucket(uid: str) -> tuple[str, str]:
    """returns (bucket, reason)."""
    profile = api('GET', f'/users/{uid}')
    if isinstance(profile, dict):
        if profile.get('primaryHospitalId'):
            return str(profile['primaryHospitalId']), 'primaryHospitalId'
        if profile.get('hospitalId'):
            return str(profile['hospitalId']), 'hospitalId'
    return 'unknown', 'fallback'


def dry_run() -> None:
    src = api('GET', '/visit_plans') or {}
    print(f'legacy /visit_plans: {len(src)} entries')
    for uid, entry in src.items():
        bucket, reason = resolve_bucket(uid)
        print(f'  - {uid[:18]}... → bucket={bucket} (via {reason}) '
              f'[source={entry.get("source","?")}, expiresAt={entry.get("expiresAt","?")}]')
    print('\nno writes performed')


def apply() -> None:
    src = api('GET', '/visit_plans') or {}
    if not src:
        print('legacy /visit_plans empty — nothing to migrate')
        return

    ts = int(time.time() * 1000)
    backup_path = f'/visit_plans_backup_{ts}'
    api('PUT', backup_path, src)
    print(f'✓ backup: {backup_path} ({len(src)} entries)')

    payload: dict = {}
    for uid, entry in src.items():
        bucket, reason = resolve_bucket(uid)
        # entry 에 hospitalId 필드 주입 (없으면 추가, 있으면 유지)
        enriched = dict(entry)
        if bucket != 'unknown':
            enriched['hospitalId'] = bucket
        payload[f'hospitals/{bucket}/visit_plans/{uid}'] = enriched
        print(f'  → hospitals/{bucket}/visit_plans/{uid[:18]}... (via {reason})')

    api('PATCH', '/', payload)
    print(f'\n✓ nested write: {len(payload)} entries')

    # Verify
    print('\n=== verify ===')
    bucket_counts: dict = {}
    for path in payload:
        bucket = path.split('/')[1]
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    for b, c in bucket_counts.items():
        written = api('GET', f'/hospitals/{b}/visit_plans') or {}
        print(f'  hospitals/{b}/visit_plans: {len(written)} entries (expected {c}+)')


def rollback(ts: str) -> None:
    backup_path = f'/visit_plans_backup_{ts}'
    data = api('GET', backup_path)
    if not data:
        print(f'backup not found at {backup_path}', file=sys.stderr)
        sys.exit(1)
    api('PUT', '/visit_plans', data)
    print(f'✓ restored /visit_plans from {backup_path} ({len(data)} entries)')
    print('NOTE: nested /hospitals/*/visit_plans entries are NOT removed by this command.')


def main() -> None:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry-run', action='store_true')
    g.add_argument('--apply', action='store_true')
    g.add_argument('--rollback', metavar='TIMESTAMP',
                   help='timestamp suffix of visit_plans_backup_{TS}')
    args = p.parse_args()

    if args.dry_run:
        dry_run()
    elif args.apply:
        apply()
    elif args.rollback:
        rollback(args.rollback)


if __name__ == '__main__':
    main()
