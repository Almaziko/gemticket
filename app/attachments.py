import os
import uuid
import mimetypes

from flask import current_app
from werkzeug.utils import secure_filename

from .extensions import db
from .models import Attachment, Settings


class FileTooLargeError(Exception):
    def __init__(self, filename, limit_mb):
        self.filename = filename
        self.limit_mb = limit_mb
        super().__init__(f'{filename} превышает лимит {limit_mb} МБ')


def get_max_upload_mb():
    settings = Settings.query.first()
    return settings.max_upload_mb if settings else 50


def check_files_size(file_storages):
    """Проверяет размер файлов ДО сохранения чего-либо. Бросает FileTooLargeError."""
    limit_mb = get_max_upload_mb()
    limit_bytes = limit_mb * 1024 * 1024
    for fs in file_storages:
        if not fs or not fs.filename:
            continue
        fs.stream.seek(0, os.SEEK_END)
        size = fs.stream.tell()
        fs.stream.seek(0)
        if size > limit_bytes:
            raise FileTooLargeError(fs.filename, limit_mb)


def save_attachment(file_storage, uploader, ticket=None, comment=None):
    original_name = file_storage.filename or 'file'
    safe_name = secure_filename(original_name) or 'file'
    ext = os.path.splitext(safe_name)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"

    upload_dir = current_app.config['UPLOAD_DIR']
    os.makedirs(upload_dir, exist_ok=True)
    full_path = os.path.join(upload_dir, stored_name)
    file_storage.save(full_path)
    size = os.path.getsize(full_path)

    mime = file_storage.mimetype or mimetypes.guess_type(safe_name)[0] or 'application/octet-stream'

    attachment = Attachment(
        filename_original=original_name,
        filename_stored=stored_name,
        size_bytes=size,
        mime_type=mime,
        uploaded_by_id=uploader.id,
        ticket_id=ticket.id if ticket else None,
        comment_id=comment.id if comment else None,
    )
    db.session.add(attachment)
    return attachment


def save_attachments(file_storages, uploader, ticket=None, comment=None):
    saved = []
    for fs in file_storages:
        if not fs or not fs.filename:
            continue
        saved.append(save_attachment(fs, uploader, ticket=ticket, comment=comment))
    return saved


def delete_attachment_file(attachment):
    path = os.path.join(current_app.config['UPLOAD_DIR'], attachment.filename_stored)
    try:
        os.remove(path)
    except OSError:
        pass


def refresh_max_content_length(app):
    """Глобальный запасной потолок Flask на тело запроса — с учётом того, что
    за раз может грузиться несколько файлов. Точная проверка размера каждого
    файла отдельно всё равно делается в check_files_size()."""
    with app.app_context():
        try:
            limit_mb = get_max_upload_mb()
        except Exception:
            limit_mb = 50
    app.config['MAX_CONTENT_LENGTH'] = limit_mb * 1024 * 1024 * 20 + 5 * 1024 * 1024
