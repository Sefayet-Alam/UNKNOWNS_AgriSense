"""Storage stays local by default and switches to Vercel Blob by env config."""
from __future__ import annotations

import json

import httpx
import pytest

from app import storage


@pytest.mark.asyncio
async def test_local_storage_round_trip_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "BLOB_READ_WRITE_TOKEN", "")
    monkeypatch.setattr(storage.settings, "UPLOAD_DIR", str(tmp_path))

    location = await storage.store_bytes(
        user_id=7,
        filename="leaf.png",
        data=b"leaf-bytes",
        mime_type="image/png",
    )

    assert location == str(tmp_path / "7" / "leaf.png")
    assert await storage.load_bytes(location) == b"leaf-bytes"


@pytest.mark.asyncio
async def test_private_blob_round_trip_uses_server_credentials(monkeypatch):
    token = "vercel_blob_rw_store123_secret456"
    blob_url = "https://store123.private.blob.vercel-storage.com/uploads/7/leaf.png"
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == f"Bearer {token}"
        if request.method == "PUT":
            assert request.headers["x-vercel-blob-store-id"] == "store123"
            assert request.headers["x-vercel-blob-access"] == "private"
            assert request.headers["x-content-type"] == "image/png"
            return httpx.Response(200, json={"url": blob_url})
        assert str(request.url) == blob_url
        return httpx.Response(200, content=b"blob-bytes")

    monkeypatch.setattr(storage.settings, "BLOB_READ_WRITE_TOKEN", token)
    monkeypatch.setattr(storage.settings, "BLOB_ACCESS", "private")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        location = await storage.store_bytes(
            user_id=7,
            filename="leaf.png",
            data=b"blob-bytes",
            mime_type="image/png",
            client=client,
        )
        assert location == blob_url
        assert await storage.load_bytes(location, client=client) == b"blob-bytes"
    finally:
        await client.aclose()
    assert [request.method for request in seen] == ["PUT", "GET"]


@pytest.mark.asyncio
async def test_blob_rejects_an_invalid_service_url(monkeypatch):
    token = "vercel_blob_rw_store123_secret456"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"url": "https://example.com/x"}))

    monkeypatch.setattr(storage.settings, "BLOB_READ_WRITE_TOKEN", token)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(storage.StorageError, match="invalid object URL"):
            await storage.store_bytes(
                user_id=7,
                filename="leaf.png",
                data=b"bytes",
                mime_type="image/png",
                client=client,
            )
    finally:
        await client.aclose()
