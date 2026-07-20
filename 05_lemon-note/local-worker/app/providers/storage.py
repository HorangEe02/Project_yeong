"""로컬 파일 저장 Provider.

경로 규칙(docs/db-schema.md): /users/{user_id}/meetings/{meeting_id}/...
서버 이전 시 SupabaseStorageProvider 로 교체하되 인터페이스는 동일.
"""
import hashlib
import os
from pathlib import Path

from .. import config


class LocalFileStorage:
    name = "local"

    def _meeting_dir(self, user_id: str, meeting_id: str) -> Path:
        d = config.DATA_ROOT / "users" / user_id / "meetings" / meeting_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_original(self, user_id: str, meeting_id: str, filename: str,
                      content: bytes) -> dict:
        ext = (os.path.splitext(filename or "")[1] or ".bin").lstrip(".").lower()
        path = self._meeting_dir(user_id, meeting_id) / f"original.{ext}"
        path.write_bytes(content)
        return {
            "path": str(path),
            "size": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
            "ext": ext,
        }

    def save_export(self, user_id: str, meeting_id: str, export_id: str,
                    ext: str, content: str) -> dict:
        d = self._meeting_dir(user_id, meeting_id) / "exports"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{export_id}.{ext}"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path)}


storage = LocalFileStorage()
