import qrcode
import os
from db import get_user, add_user

def ensure_qrcode_dir():
    os.makedirs('qrcodes', exist_ok=True)

def generate_qr_for_user(user_id: str, payload: str):
    ensure_qrcode_dir()
    img = qrcode.make(payload)
    path = os.path.join('qrcodes', f'{user_id}.png')
    img.save(path)
    return path

def generate_qr_from_db():
    # Expect users already in DB; we'll fetch using sqlite directly to iterate
    import sqlite3
    conn = sqlite3.connect('attendance.db')
    cur = conn.cursor()
    cur.execute('SELECT id, name, roll, email FROM users')
    rows = cur.fetchall()
    conn.close()
    ensure_qrcode_dir()
    created = []
    for r in rows:
        user_id = r[0]
        # payload: simple JSON-like string; scanner will read this whole string.
        payload = f"{{'id':'{user_id}','name':'{r[1]}','roll':'{r[2]}','email':'{r[3]}'}}"
        img = qrcode.make(payload)
        path = os.path.join('qrcodes', f'{user_id}.png')
        img.save(path)
        created.append(path)
    return created

if __name__ == '__main__':
    created = generate_qr_from_db()
    print('Generated', len(created), 'QR files in qrcodes/')