"""
Работа с паролями пользователей и SMTP-паролем в настройках.

Пароль хранится в двух видах:
- password_hash: SHA-256 (hex) — уникальный индексированный столбец для
  быстрого поиска учётки по введённому паролю при логине (без перебора и
  расшифровки всей таблицы) и для проверки глобальной уникальности пароля.
- password_encrypted: шифротекст Fernet — обратимый, нужен только чтобы
  админ мог посмотреть пароль клиента в интерфейсе.

Отдельного "хеша для безопасности" здесь нет: раз пароль в любом случае можно
расшифровать через Fernet, дополнительная стойкость sha256 как второго слоя
не требуется — он используется исключительно как быстрый индекс.
"""
import hashlib

from cryptography.fernet import Fernet
from flask import current_app


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _get_fernet() -> Fernet:
    key = current_app.config['FERNET_KEY']
    if not key:
        raise RuntimeError('FERNET_KEY не задан в переменных окружения')
    return Fernet(key)


def encrypt_secret(plain: str) -> bytes:
    return _get_fernet().encrypt(plain.encode('utf-8'))


def decrypt_secret(token: bytes) -> str:
    return _get_fernet().decrypt(token).decode('utf-8')
