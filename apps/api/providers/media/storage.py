"""Object storage: Cloudflare R2 (S3 API) when configured, else the local filesystem (dev/CI)."""

import shutil
import tempfile
from pathlib import Path

from config import settings


def _r2_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def use_r2() -> bool:
    return bool(settings.r2_account_id and settings.r2_bucket)


def put_file(local_path: Path, key: str, content_type: str) -> None:
    if use_r2():
        # upload_file switches to multipart automatically for large videos.
        _r2_client().upload_file(str(local_path), settings.r2_bucket, key, ExtraArgs={"ContentType": content_type})
        return
    dest = settings.local_media_dir / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local_path, dest)


def public_url(key: str | None) -> str | None:
    if not key:
        return None
    if key.startswith("http://") or key.startswith("https://") or key.startswith("/"):
        return key
    return f"{settings.media_public_base.rstrip('/')}/{key}"


def fetch_to_local(key: str) -> Path:
    """Returns a local path for processing (ffmpeg). Caller must not delete local-mode files."""
    if use_r2():
        tmp = Path(tempfile.mkdtemp()) / Path(key).name
        _r2_client().download_file(settings.r2_bucket, key, str(tmp))
        return tmp
    return settings.local_media_dir / key


def exists(key: str) -> bool:
    if use_r2():
        try:
            _r2_client().head_object(Bucket=settings.r2_bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001  (any client error means "not there")
            return False
    return (settings.local_media_dir / key).exists()
