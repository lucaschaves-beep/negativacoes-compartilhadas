import hashlib
import boto3
from botocore.config import Config
from app.config import get_settings

settings = get_settings()


def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key,
        aws_secret_access_key=settings.r2_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def compute_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def upload_to_r2(image_bytes: bytes, filename: str, card_id: str) -> str:
    """Faz upload para Cloudflare R2 e retorna a URL pública."""
    if not settings.r2_account_id:
        return ""

    file_hash = compute_hash(image_bytes)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    key = f"evidencias/{card_id}/{file_hash}.{ext}"

    content_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"

    client = _get_r2_client()
    client.put_object(
        Bucket=settings.r2_bucket,
        Key=key,
        Body=image_bytes,
        ContentType=content_type,
    )

    return f"{settings.r2_public_url}/{key}" if settings.r2_public_url else key
