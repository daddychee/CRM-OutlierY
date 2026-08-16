"""Mã hóa API key trong DB (Fernet) — bật từ Phase 4 khi app có thể lộ ra internet.

Khóa chủ: env RADARY_SECRET (ưu tiên, dùng cho Docker/VPS) hoặc file data/secret.key
(tự sinh lần đầu, chmod 600). MẤT KHÓA CHỦ = MẤT API KEY đã mã hóa — backup data/
phải gồm cả secret.key.

Tương thích ngược: giá trị chưa mã hóa (trước Phase 4) đọc được bình thường;
server tự nâng cấp chúng thành bản mã hóa lúc khởi động (encrypt_existing).
"""
import os

DATA = os.environ.get('RADARY_DATA_DIR') or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
KEY_PATH = os.path.join(DATA, 'secret.key')
_PREFIX = 'gAAAA'          # mọi Fernet token bắt đầu bằng chuỗi này

def _master_key():
    k = os.environ.get('RADARY_SECRET', '').strip()
    if k: return k.encode()
    if os.path.exists(KEY_PATH):
        return open(KEY_PATH, 'rb').read().strip()
    from cryptography.fernet import Fernet
    k = Fernet.generate_key()
    os.makedirs(DATA, exist_ok=True)
    with open(KEY_PATH, 'wb') as f: f.write(k)
    os.chmod(KEY_PATH, 0o600)
    return k

def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(_master_key())

def encrypt(plain):
    return _fernet().encrypt(plain.encode()).decode()

def decrypt(stored):
    if not stored.startswith(_PREFIX):
        return stored              # plaintext cũ (trước Phase 4) — vẫn đọc được
    try:
        return _fernet().decrypt(stored.encode()).decode()
    except ImportError:
        raise RuntimeError('Key trong DB đã mã hóa — cần chạy bằng .venv (pip install -r requirements.txt)')

def encrypt_existing(conn):
    """Nâng cấp tại chỗ các key còn plaintext. Gọi lúc server khởi động."""
    n = 0
    for r in conn.execute('SELECT id, key FROM api_keys').fetchall():
        if not r['key'].startswith(_PREFIX):
            conn.execute('UPDATE api_keys SET key=? WHERE id=?', (encrypt(r['key']), r['id'])); n += 1
    if n: conn.commit()
    return n
