"""
对象存储：本地磁盘（默认）与 MinIO/S3（生产）双实现。
需求：图片上传单图不超过 5MB，格式 jpg/png/webp，需经病毒扫描与敏感内容检测（此处留可插拔钩子）。
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from ..core.config import (
    PUBLIC_BASE_URL,
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_REGION,
    S3_SECRET_KEY,
    STORAGE_TYPE,
    UPLOAD_DIR,
)

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB


class UploadError(Exception):
    pass


def _scan(file_bytes: bytes, filename: str) -> None:
    """安全扫描钩子：预留接入病毒扫描与敏感内容检测服务"""
    if len(file_bytes) > MAX_SIZE:
        raise UploadError(f"图片 {filename} 超过 5MB 限制")
    # TODO: 接入学校统一病毒扫描 / 敏感内容检测 API


def save_image(file: UploadFile) -> str:
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise UploadError("仅支持 jpg / png / webp 格式")
    data = file.file.read()
    _scan(data, file.filename or "")
    name = f"{uuid.uuid4().hex}.{ext}"

    if STORAGE_TYPE == "s3":
        try:
            import boto3  # type: ignore
            from botocore.client import Config  # type: ignore

            s3 = boto3.client(
                "s3",
                endpoint_url=S3_ENDPOINT,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                region_name=S3_REGION,
                config=Config(signature_version="s3v4"),
            )
            s3.put_object(Bucket=S3_BUCKET, Key=name, Body=data, ContentType=file.content_type or "image/jpeg")
            return f"{PUBLIC_BASE_URL or S3_ENDPOINT}/{S3_BUCKET}/{name}"
        except UploadError:
            raise
        except Exception as e:
            raise UploadError(f"对象存储不可用：{e}")

    dest: Path = UPLOAD_DIR / name
    dest.write_bytes(data)
    return f"/static/uploads/{name}"
