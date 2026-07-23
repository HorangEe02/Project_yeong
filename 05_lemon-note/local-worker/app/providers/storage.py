"""파일 저장 Provider — local(로컬 디스크) | supabase(Supabase Storage).

경로 규칙(docs/db-schema.md): users/{user_id}/meetings/{meeting_id}/...
`config.STORAGE_PROVIDER` 로 교체하며, 상위 코드(main.py)는 인터페이스만 사용한다.

인터페이스
  save_original(user_id, meeting_id, filename, content: bytes) -> {path,size,checksum,ext}
  save_export(user_id, meeting_id, export_id, ext, content: str) -> {path}
  size(path) -> int | None
  read_all(path) -> bytes | None
  read_range(path, start, end) -> bytes | None     # end 포함(inclusive)

DB 의 storage_path 에는 각 Provider 가 해석할 수 있는 경로가 저장된다
(local = 절대 파일경로, supabase = 버킷 내 object key). Provider 를 바꾸면 이전에 저장된
파일은 이전 Provider 경로를 가리키므로, 전환 시점 이후 업로드분부터 새 저장소를 쓴다.
"""
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import config


# ---------------------------------------------------------------- local
class LocalFileStorage:
    name = "local"

    def _meeting_dir(self, user_id: str, meeting_id: str) -> Path:
        d = config.DATA_ROOT / "users" / user_id / "meetings" / meeting_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_original(self, user_id, meeting_id, filename, content: bytes) -> dict:
        ext = (os.path.splitext(filename or "")[1] or ".bin").lstrip(".").lower()
        path = self._meeting_dir(user_id, meeting_id) / f"original.{ext}"
        path.write_bytes(content)
        return {"path": str(path), "size": len(content),
                "checksum": hashlib.sha256(content).hexdigest(), "ext": ext}

    def create_signed_upload(self, user_id, meeting_id, ext: str) -> dict:
        """로컬 저장소에는 직접 업로드 대상이 없다. 호출측이 기존 multipart 로 돌아간다."""
        return {}

    def stat_uploaded(self, key: str) -> dict:
        return {}

    def save_export(self, user_id, meeting_id, export_id, ext, content: str) -> dict:
        d = self._meeting_dir(user_id, meeting_id) / "exports"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{export_id}.{ext}"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path)}

    def size(self, path):
        return os.path.getsize(path) if path and os.path.exists(path) else None

    def read_all(self, path):
        if not path or not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def read_range(self, path, start: int, end: int):
        if not path or not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            f.seek(start)
            return f.read(end - start + 1)


# ------------------------------------------------------------- supabase
class SupabaseStorage:
    """Supabase Storage(비공개 버킷). 서버측 service_role 키로만 접근한다.

    표준 라이브러리(urllib)만 사용해 추가 의존성이 없다.
    """

    name = "supabase"

    def __init__(self):
        if not config.SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL 이 설정되지 않았습니다.")
        if not config.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_SERVICE_ROLE_KEY 가 필요합니다(비공개 버킷 접근용). "
                ".env 에 Settings > API 의 service_role 키를 넣으세요.")
        self.base = config.SUPABASE_URL.rstrip("/")
        self.bucket = config.SUPABASE_BUCKET

    # --- 내부 헬퍼 ---
    def _url(self, key: str) -> str:
        return f"{self.base}/storage/v1/object/{self.bucket}/{urllib.parse.quote(key)}"

    def _headers(self, extra=None) -> dict:
        h = {"Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
             "apikey": config.SUPABASE_SERVICE_ROLE_KEY}
        if extra:
            h.update(extra)
        return h

    def _upload(self, key: str, data: bytes, content_type: str) -> None:
        req = urllib.request.Request(
            self._url(key), data=data, method="POST",
            headers=self._headers({"Content-Type": content_type,
                                   "x-upsert": "true"}))
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()

    def _get(self, key: str, range_header=None):
        extra = {"Range": range_header} if range_header else None
        req = urllib.request.Request(self._url(key), method="GET",
                                     headers=self._headers(extra))
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None, {}
            raise

    # --- 인터페이스 ---
    @staticmethod
    def _key(user_id, meeting_id, *parts) -> str:
        return "/".join(["users", str(user_id), "meetings", str(meeting_id), *parts])

    def save_original(self, user_id, meeting_id, filename, content: bytes) -> dict:
        ext = (os.path.splitext(filename or "")[1] or ".bin").lstrip(".").lower()
        key = self._key(user_id, meeting_id, f"original.{ext}")
        self._upload(key, content, "application/octet-stream")
        return {"path": key, "size": len(content),
                "checksum": hashlib.sha256(content).hexdigest(), "ext": ext}

    def create_signed_upload(self, user_id, meeting_id, ext: str) -> dict:
        """브라우저가 서버를 거치지 않고 직접 올릴 수 있는 1회용 업로드 URL.

        Vercel 서버리스는 요청 본문이 4.5MB 로 제한돼 있어, 파일이 API 를 통과하는
        구조로는 2분 남짓의 녹음도 올릴 수 없다. 브라우저 → Storage 직접 업로드로
        그 제한을 우회한다(서버는 경로만 받는다).
        """
        key = self._key(user_id, meeting_id, f"original.{ext}")
        url = f"{self.base}/storage/v1/object/upload/sign/{self.bucket}/{urllib.parse.quote(key)}"
        req = urllib.request.Request(url, data=b"{}", method="POST",
                                     headers=self._headers({"Content-Type": "application/json"}))
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read() or b"{}")
        # Supabase 는 {"url": "/object/upload/sign/<bucket>/<key>?token=..."} 를 돌려준다.
        signed = body.get("url") or ""
        if signed.startswith("/"):
            signed = f"{self.base}/storage/v1{signed}"
        return {"upload_url": signed, "path": key, "token": body.get("token")}

    def stat_uploaded(self, key: str) -> dict:
        """직접 업로드된 객체의 크기·체크섬을 서버가 확인한다.

        클라이언트가 보고한 값을 그대로 믿지 않기 위함이다. 파일을 한 번 읽으므로
        서버리스 메모리 안에서 처리 가능한 크기여야 한다(응답 본문 제한과는 무관).
        """
        data, _ = self._get(key)
        if data is None:
            return {}
        return {"path": key, "size": len(data),
                "checksum": hashlib.sha256(data).hexdigest()}

    def save_export(self, user_id, meeting_id, export_id, ext, content: str) -> dict:
        key = self._key(user_id, meeting_id, "exports", f"{export_id}.{ext}")
        self._upload(key, content.encode("utf-8"),
                     "text/markdown; charset=utf-8" if ext == "md"
                     else "text/plain; charset=utf-8")
        return {"path": key}

    def size(self, path):
        """1바이트만 Range 로 받아 Content-Range 의 전체 길이를 읽는다."""
        if not path:
            return None
        data, headers = self._get(path, "bytes=0-0")
        if data is None:
            return None
        cr = headers.get("Content-Range") or headers.get("content-range")
        if cr and "/" in cr:
            try:
                return int(cr.rsplit("/", 1)[1])
            except ValueError:
                pass
        full, _ = self._get(path)
        return len(full) if full is not None else None

    def read_all(self, path):
        if not path:
            return None
        data, _ = self._get(path)
        return data

    def read_range(self, path, start: int, end: int):
        if not path:
            return None
        data, _ = self._get(path, f"bytes={start}-{end}")
        return data


def get_storage():
    if config.STORAGE_PROVIDER == "supabase":
        return SupabaseStorage()
    return LocalFileStorage()


storage = get_storage()
