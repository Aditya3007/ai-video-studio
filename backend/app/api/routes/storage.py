"""Storage verification route."""

from fastapi import APIRouter

from app.api.deps import StorageDep
from app.api.errors import AppError

router = APIRouter(prefix="/storage", tags=["storage"])


@router.post("/test")
def test_storage(storage: StorageDep) -> dict[str, str | bool]:
    """Verify the configured storage backend by writing, reading, and deleting."""
    key = "__healthcheck__/ping.txt"
    try:
        storage.put(key, b"ok", content_type="text/plain")
        body = storage.get(key)
        data = body.read()
        body.close()
        storage.delete(key)
    except Exception as exc:
        raise AppError("STORAGE_ERROR", str(exc), status_code=500) from exc

    if data != b"ok":
        raise AppError(
            "STORAGE_MISMATCH",
            "Read bytes did not match written bytes",
            status_code=500,
        )

    return {"ok": True, "backend": type(storage).__name__}
