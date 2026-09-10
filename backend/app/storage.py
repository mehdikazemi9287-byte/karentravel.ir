"""Persistent media/document storage for supplier-owned assets.

Every blob lives under a single configured root (``MEDIA_STORAGE_ROOT``) which in
production is an explicitly mounted Docker volume, so uploads survive container
recreation and can be backed up as one tree. Endpoints never touch the
filesystem directly; they go through this module, which builds safe,
tenant-scoped keys and contains every path inside the storage root.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
from pathlib import Path
from typing import Final

from .config import read_secret

# tenant/{int}/supplier/{uuid}/{entity_type}/{uuid}/{32-hex}.{ext}
_KEY_RE: Final = re.compile(
    r"^tenant/[1-9][0-9]{0,17}/supplier/[0-9a-fA-F-]{36}/[a-z_]{2,40}/[0-9a-fA-F-]{36}/[0-9a-f]{32}\.[a-z0-9]{2,5}$"
)
_ID_RE: Final = re.compile(r"^[0-9a-fA-F-]{36}$")
_ENTITY_RE: Final = re.compile(r"^[a-z_]{2,40}$")
_EXT_RE: Final = re.compile(r"^[a-z0-9]{2,5}$")

IMAGE_TYPES: Final[dict[str, str]] = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "gif": "image/gif",
}
DOCUMENT_TYPES: Final[dict[str, str]] = {
    "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
}
_MAGIC: Final[dict[str, tuple[bytes, ...]]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF-",),
}
MAX_IMAGE_BYTES: Final = 5 * 1024 * 1024
MAX_DOCUMENT_BYTES: Final = 15 * 1024 * 1024


class StorageError(ValueError):
    """Raised for any unsafe or invalid upload/key; callers map this to HTTP 422."""


def storage_root() -> Path:
    root = Path(read_secret("MEDIA_STORAGE_ROOT", "/app/media")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_key(*, tenant_id: int, supplier_id: str, entity_type: str, entity_id: str, ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if not _EXT_RE.match(ext):
        raise StorageError("پسوند فایل نامعتبر است")
    if not _ENTITY_RE.match(entity_type):
        raise StorageError("نوع موجودیت نامعتبر است")
    if not _ID_RE.match(str(supplier_id)) or not _ID_RE.match(str(entity_id)):
        raise StorageError("شناسه نامعتبر است")
    if int(tenant_id) <= 0:
        raise StorageError("tenant نامعتبر است")
    return f"tenant/{int(tenant_id)}/supplier/{supplier_id}/{entity_type}/{entity_id}/{uuid.uuid4().hex}.{ext}"


def _resolve(key: str) -> Path:
    if not isinstance(key, str) or not _KEY_RE.match(key):
        raise StorageError("کلید ذخیره‌سازی نامعتبر است")
    root = storage_root()
    path = (root / key).resolve()
    if path != root and root not in path.parents:
        raise StorageError("مسیر ذخیره‌سازی خارج از محدوده مجاز است")
    return path


def write_blob(key: str, data: bytes) -> None:
    path = _resolve(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f"{path.name}.{uuid.uuid4().hex}.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, path)


def read_blob(key: str) -> bytes:
    return _resolve(key).read_bytes()


def delete_blob(key: str) -> None:
    try:
        _resolve(key).unlink()
    except (FileNotFoundError, StorageError):
        pass


def blob_exists(key: str) -> bool:
    try:
        return _resolve(key).exists()
    except StorageError:
        return False


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_upload(*, kind: str, filename: str, content_type: str, data: bytes) -> tuple[str, str]:
    """Return ``(ext, canonical_content_type)`` for a safe upload, else raise StorageError."""
    filename = filename or ""
    if "\x00" in filename or "/" in filename or "\\" in filename or ".." in filename:
        raise StorageError("نام فایل نامعتبر است")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = IMAGE_TYPES if kind == "image" else DOCUMENT_TYPES
    if ext not in allowed:
        raise StorageError("نوع فایل مجاز نیست")
    canonical = allowed[ext]
    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_DOCUMENT_BYTES
    if not data:
        raise StorageError("فایل خالی است")
    if len(data) > limit:
        raise StorageError("حجم فایل از حد مجاز بیشتر است")
    magics = _MAGIC.get(canonical, ())
    if magics and not any(data.startswith(m) for m in magics):
        raise StorageError("محتوای فایل با نوع اعلام‌شده مطابقت ندارد")
    if canonical == "image/webp" and data[8:12] != b"WEBP":
        raise StorageError("محتوای فایل با نوع اعلام‌شده مطابقت ندارد")
    head = data[:2048]
    lowered = head.lower()
    if (
        head[:2] == b"MZ" or head[:4] == b"\x7fELF" or head.startswith(b"#!")
        or head[:4] == b"PK\x03\x04" or b"<?php" in lowered or b"<script" in lowered
    ):
        raise StorageError("محتوای اجرایی یا اسکریپتی مجاز نیست")
    if canonical.startswith("image/"):
        _verify_image(data)
    return ext, canonical


def _verify_image(data: bytes) -> None:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a hard dependency in prod
        return
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except Exception as exc:  # noqa: BLE001
        raise StorageError("تصویر معتبر نیست") from exc
