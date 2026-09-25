"""
S3-совместимое объектное хранилище для НОВЫХ вложений тикетов (см.
Settings.s3_* в models.py) — чтобы не упираться в место на диске сервера.
Настраивается в админке (Настройки -> Хранилище вложений). Если не
настроено, attachments.py как и раньше сохраняет файлы на локальный диск.

Бакет должен быть приватным: скачивание идёт через собственный роут
tickets.download_attachment, который сначала проверяет can_view_attachment
и только потом просит presigned-URL — без этого чужие вложения можно было
бы скачать напрямую с S3 в обход прав доступа.
"""
import boto3
from botocore.client import Config

from .security import decrypt_secret


def s3_configured(settings):
    return bool(
        settings and settings.s3_endpoint and settings.s3_bucket
        and settings.s3_access_key and settings.s3_secret_key_encrypted
    )


def build_key(settings, name):
    """Ключ объекта с учётом настроенного префикса ("папки") — вызывается
    только при загрузке НОВОГО файла, а не при каждом обращении: итоговый
    ключ сохраняется как Attachment.filename_stored, так что уже
    загруженные файлы не потеряются, даже если префикс потом сменят."""
    prefix = (settings.s3_prefix or '').strip('/')
    return f'{prefix}/{name}' if prefix else name


def get_s3_client(settings):
    return boto3.client(
        's3',
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=decrypt_secret(settings.s3_secret_key_encrypted),
        config=Config(signature_version='s3v4'),
    )


def upload_fileobj(settings, file_storage, key, content_type):
    client = get_s3_client(settings)
    file_storage.stream.seek(0)
    client.upload_fileobj(
        file_storage.stream, settings.s3_bucket, key,
        ExtraArgs={'ContentType': content_type},
    )


def delete_object(settings, key):
    client = get_s3_client(settings)
    client.delete_object(Bucket=settings.s3_bucket, Key=key)


def generate_download_url(settings, key, download_name, content_type, as_attachment, expires_in=60):
    client = get_s3_client(settings)
    disposition = 'attachment' if as_attachment else 'inline'
    return client.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': settings.s3_bucket,
            'Key': key,
            'ResponseContentType': content_type,
            'ResponseContentDisposition': f'{disposition}; filename="{download_name}"',
        },
        ExpiresIn=expires_in,
    )
