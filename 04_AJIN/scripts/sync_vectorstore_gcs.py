"""ChromaDB vectorstore ↔ GCS 동기화 (풀 모드 배포용).

이미지 baking 대신 GCS 영속화를 쓰면:
  - 이미지 사이즈 감소 (vectorstore 14MB 제외)
  - RAG 문서 추가 시 재배포 없이 sync 만으로 반영
  - 멀티 인스턴스 시 일관성 (각 인스턴스가 동일한 GCS 인덱스 다운로드)

버킷: gs://ajin-cb-vectorstore (사용자가 만들어야 함)
  gcloud storage buckets create gs://ajin-cb-vectorstore --location=asia-northeast3 --project=ajin-cb

실행:
  python scripts/sync_vectorstore_gcs.py upload    # 로컬 → GCS
  python scripts/sync_vectorstore_gcs.py download  # GCS → 로컬 (Cloud Run 부팅 시)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_LOCAL_DIR = PROJECT_ROOT / "vectorstore"
DEFAULT_BUCKET = os.environ.get("VECTORSTORE_BUCKET", "ajin-cb-vectorstore")
DEFAULT_PREFIX = os.environ.get("VECTORSTORE_PREFIX", "vectorstore/")


def upload(local_dir: Path, bucket_name: str, prefix: str) -> int:
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    if not local_dir.exists():
        print(f"⚠️ 로컬 디렉토리 없음: {local_dir}")
        return 0

    uploaded = 0
    for local_path in local_dir.rglob("*"):
        if local_path.is_dir():
            continue
        rel = local_path.relative_to(local_dir).as_posix()
        blob_name = f"{prefix.rstrip('/')}/{rel}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_path))
        uploaded += 1
        if uploaded % 20 == 0:
            print(f"  ↑ {uploaded} files...")

    print(f"✓ Upload 완료: {uploaded} files → gs://{bucket_name}/{prefix}")
    return uploaded


def download(local_dir: Path, bucket_name: str, prefix: str) -> int:
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    local_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    blobs = list(client.list_blobs(bucket_name, prefix=prefix))
    print(f"  GCS 에서 {len(blobs)}개 객체 발견")

    for blob in blobs:
        rel = blob.name[len(prefix):].lstrip("/")
        if not rel:
            continue
        target = local_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(target))
        downloaded += 1
        if downloaded % 20 == 0:
            print(f"  ↓ {downloaded} files...")

    print(f"✓ Download 완료: {downloaded} files → {local_dir}")
    return downloaded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["upload", "download"])
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--local", default=str(DEFAULT_LOCAL_DIR))
    args = parser.parse_args()

    local_dir = Path(args.local)
    print(f"동작: {args.action}")
    print(f"로컬: {local_dir}")
    print(f"GCS: gs://{args.bucket}/{args.prefix}")
    print()

    if args.action == "upload":
        n = upload(local_dir, args.bucket, args.prefix)
    else:
        n = download(local_dir, args.bucket, args.prefix)

    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
