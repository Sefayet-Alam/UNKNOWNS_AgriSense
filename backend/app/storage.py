"""Upload storage with a local-disk default and Vercel Blob backend.

Docker and local development keep the original user-scoped filesystem
behavior.  When ``BLOB_READ_WRITE_TOKEN`` is configured, uploaded bytes are
stored in Vercel Blob and the private Blob URL is persisted in the existing
``attachments.path`` column.  Reads remain authenticated by AgriSense and are
proxied through the API; the Blob credential is never exposed to the browser.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

from .config import settings

log = logging.getLogger("agrisense.storage")

_BLOB_API_VERSION = "12"
_BLOB_HOST_SUFFIX = ".blob.vercel-storage.com"


class StorageError(RuntimeError):
    """The configured upload store could not save or retrieve an object."""


def uses_blob_storage() -> bool:
    return bool(settings.BLOB_READ_WRITE_TOKEN.strip())


def is_blob_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(
        parsed.hostname and parsed.hostname.endswith(_BLOB_HOST_SUFFIX)
    )


def _blob_store_id(token: str) -> str:
    # Vercel read/write tokens have the documented
    # ``vercel_blob_rw_<store-id>_<secret>`` shape.  Only the store id is sent
    # separately; the complete token remains in the Authorization header.
    parts = token.split("_")
    if len(parts) < 5 or not parts[3]:
        raise StorageError("invalid BLOB_READ_WRITE_TOKEN format")
    return parts[3]


def is_configured_blob_url(value: str) -> bool:
    """Return true only for an object owned by the configured Blob store."""
    if not is_blob_url(value):
        return False
    token = settings.BLOB_READ_WRITE_TOKEN.strip()
    if not token:
        return False
    try:
        store_id = _blob_store_id(token)
        hostname = urlsplit(value).hostname or ""
    except (StorageError, ValueError):
        return False
    return hostname.startswith(f"{store_id}.")


async def _blob_put(
    pathname: str,
    data: bytes,
    mime_type: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    token = settings.BLOB_READ_WRITE_TOKEN.strip()
    store_id = _blob_store_id(token)
    request_id = f"{store_id}:{uuid.uuid4().hex}"
    endpoint = settings.VERCEL_BLOB_API_URL.rstrip("/") + "/?" + urlencode(
        {"pathname": pathname}
    )
    headers = {
        "authorization": f"Bearer {token}",
        "x-api-version": _BLOB_API_VERSION,
        "x-api-blob-request-id": request_id,
        "x-api-blob-request-attempt": "0",
        "x-vercel-blob-store-id": store_id,
        "x-vercel-blob-access": settings.BLOB_ACCESS,
        "x-content-type": mime_type,
        "x-content-length": str(len(data)),
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "0",
    }
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await http.put(endpoint, content=data, headers=headers)
        response.raise_for_status()
        payload = response.json()
        url = str(payload.get("url") or "")
        if not is_blob_url(url):
            raise StorageError("Vercel Blob returned an invalid object URL")
        return url
    except (httpx.HTTPError, ValueError) as exc:
        raise StorageError(f"Vercel Blob upload failed: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()


async def store_bytes(
    *,
    user_id: int,
    filename: str,
    data: bytes,
    mime_type: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Persist bytes and return the path/URL stored in ``Attachment.path``."""
    if uses_blob_storage():
        pathname = f"uploads/{user_id}/{filename}"
        return await _blob_put(pathname, data, mime_type, client=client)

    user_dir = Path(settings.UPLOAD_DIR) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / filename
    destination.write_bytes(data)
    return str(destination)


async def load_bytes(
    location: str, *, client: httpx.AsyncClient | None = None
) -> bytes:
    """Read a local attachment or authenticated Vercel Blob object."""
    if not is_blob_url(location):
        try:
            return Path(location).read_bytes()
        except OSError as exc:
            raise StorageError(f"local attachment unavailable: {exc}") from exc

    headers = {}
    token = settings.BLOB_READ_WRITE_TOKEN.strip()
    if token:
        headers["authorization"] = f"Bearer {token}"
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await http.get(location, headers=headers)
        if response.status_code == 404:
            raise StorageError("attachment not found in Vercel Blob")
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as exc:
        raise StorageError(f"Vercel Blob download failed: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()
