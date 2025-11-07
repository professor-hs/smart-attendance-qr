import sqlite3
from typing import Optional, List, Tuple

DB_PATH = 'attendance.db'

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    try:
        cur = conn.cursor()
        # Improve concurrency and reduce lock contention
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.close()
    except Exception:
        pass
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        roll TEXT,
        email TEXT
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        date TEXT DEFAULT (date('now'))
    )
    ''')
    # Migration: ensure 'date' column exists on existing DBs
    cur.execute("PRAGMA table_info('attendance')")
    att_cols = [r[1] for r in cur.fetchall()]
    if 'date' not in att_cols:
        cur.execute("ALTER TABLE attendance ADD COLUMN date TEXT DEFAULT (date('now'))")
    # Ensure unique index on (user_id, date)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_att_unique ON attendance(user_id, date)")
    # Migrations: add columns to users if not present
    cur.execute("PRAGMA table_info('users')")
    cols = [r[1] for r in cur.fetchall()]
    if 'role' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'student'")
    cur.execute("PRAGMA table_info('users')")
    cols = [r[1] for r in cur.fetchall()]
    if 'password_hash' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

    # New tables for session-based attendance
    cur.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        date TEXT NOT NULL DEFAULT (date('now'))
    )
    ''')
    # Migration: add subject and faculty_id to sessions
    cur.execute("PRAGMA table_info('sessions')")
    sess_cols = [r[1] for r in cur.fetchall()]
    if 'subject' not in sess_cols:
        cur.execute("ALTER TABLE sessions ADD COLUMN subject TEXT DEFAULT ''")
    cur.execute("PRAGMA table_info('sessions')")
    sess_cols = [r[1] for r in cur.fetchall()]
    if 'faculty_id' not in sess_cols:
        cur.execute("ALTER TABLE sessions ADD COLUMN faculty_id TEXT")
    cur.execute('''
    CREATE TABLE IF NOT EXISTS session_attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        marked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, user_id)
    )
    ''')
    # Enrollment table: which students belong to which faculty and subject
    cur.execute('''
    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        faculty_id TEXT NOT NULL,
        subject TEXT NOT NULL,
        UNIQUE(student_id, faculty_id, subject)
    )
    ''')
    # Subjects master table (optional, subject names referenced by text)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS subjects (
        name TEXT PRIMARY KEY
    )
    ''')
    conn.commit()
    # Seed minimal data if empty
    cur.execute('SELECT COUNT(*) FROM users')
    total_users = cur.fetchone()[0]
    if total_users == 0:
        seed_sample_data(cur)
    # Always ensure admin exists and set default passwords for students lacking one
    ensure_admin_and_defaults(cur)
    # Ensure extended dataset: 7 faculties, 70 students, 7 subjects, enrollments and baseline sessions
    ensure_extended_dataset(cur)
    conn.commit()
    conn.close()

def add_user(user_id: str, name: str, roll: str = '', email: str = ''):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO users (id, name, roll, email) VALUES (?, ?, ?, ?)', (user_id, name, roll, email))
    conn.commit()
    conn.close()

def add_users_from_list(rows: List[Tuple[str,str,str,str]]):
    for r in rows:
        add_user(r[0], r[1], r[2], r[3])

def get_user(user_id: str) -> Optional[Tuple[str,str,str,str]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, name, roll, email FROM users WHERE id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def delete_session(session_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM session_attendance WHERE session_id = ?', (session_id,))
    cur.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()

def delete_all_sessions() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM session_attendance')
    cur.execute('DELETE FROM sessions')
    conn.commit()
    conn.close()

def reassign_session_faculty(session_id: int, faculty_id: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE sessions SET faculty_id = ? WHERE id = ?', (faculty_id, session_id))
    conn.commit()
    conn.close()

def student_subject_summary(user_id: str) -> List[Tuple[str, int, int, float]]:
    """Return list of (subject, attended, total, percent) for subjects the student is enrolled in."""
    conn = get_conn()
    cur = conn.cursor()
    # subjects the student is enrolled in
    cur.execute('SELECT DISTINCT subject, faculty_id FROM enrollments WHERE student_id = ?', (user_id,))
    subs = cur.fetchall()
    results: List[Tuple[str,int,int,float]] = []
    for subject, faculty_id in subs:
        # total sessions for that faculty+subject
        cur.execute('SELECT COUNT(*) FROM sessions WHERE subject = ? AND faculty_id = ?', (subject, faculty_id))
        total = cur.fetchone()[0]
        # attended sessions for this student within those sessions
        cur.execute('''
            SELECT COUNT(*)
            FROM session_attendance sa
            JOIN sessions s ON s.id = sa.session_id
            WHERE sa.user_id = ? AND s.subject = ? AND s.faculty_id = ?
        ''', (user_id, subject, faculty_id))
        attended = cur.fetchone()[0]
        percent = (attended / total * 100.0) if total > 0 else 0.0
        results.append((subject, attended, total, percent))
    conn.close()
    return results

def list_faculty_subjects(faculty_id: str) -> List[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT DISTINCT subject FROM enrollments WHERE faculty_id = ? ORDER BY subject', (faculty_id,))
    subs = [r[0] for r in cur.fetchall()]
    conn.close()
    return subs

def count_sessions_for(faculty_id: str, subject: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM sessions WHERE faculty_id = ? AND subject = ?', (faculty_id, subject))
    n = cur.fetchone()[0]
    conn.close()
    return n

def list_subjects() -> List[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT name FROM subjects ORDER BY name')
    names = [r[0] for r in cur.fetchall()]
    conn.close()
    return names

def upsert_subject(name: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO subjects (name) VALUES (?)', (name.strip(),))
    conn.commit()
    conn.close()

def delete_subject(name: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM subjects WHERE name = ?', (name.strip(),))
    conn.commit()
    conn.close()

def set_user_password(user_id: str, password_hash: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    conn.commit()
    conn.close()

def mark_attendance(user_id: str) -> bool:
    """Marks attendance for user_id. Returns True if newly inserted, False if already present today."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO attendance (user_id) VALUES (?)', (user_id,))
        conn.commit()
        inserted = cur.rowcount > 0
    except sqlite3.IntegrityError:
        # unique constraint violated (already marked today)
        inserted = False
    conn.close()
    return inserted

def export_attendance_csv(out_path: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    SELECT a.id, a.user_id, u.name, u.roll, a.timestamp
    FROM attendance a LEFT JOIN users u ON a.user_id = u.id
    ORDER BY a.timestamp
    ''')
    rows = cur.fetchall()
    conn.close()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('att_id,user_id,name,roll,timestamp\n')
        for r in rows:
            f.write(','.join([str(x) for x in r]) + '\n')

# New helpers for web app
def upsert_user_with_auth(user_id: str, name: str, roll: str, email: str, role: str, password_hash: Optional[str]):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO users (id, name, roll, email, role, password_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            roll=excluded.roll,
            email=excluded.email,
            role=excluded.role,
            password_hash=COALESCE(excluded.password_hash, users.password_hash)
    ''', (user_id, name, roll, email, role, password_hash))
    conn.commit()
    conn.close()

def get_user_auth(user_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, name, roll, email, role, password_hash FROM users WHERE id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_user_by_roll(roll: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, roll, email, role, password_hash FROM users WHERE role='student' AND roll = ?", (roll,))
    row = cur.fetchone()
    conn.close()
    return row

def list_students() -> List[Tuple[str,str,str,str]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, roll, email FROM users WHERE role='student' ORDER BY roll")
    rows = cur.fetchall()
    conn.close()
    return rows

def create_session(name: str, date: Optional[str] = None, subject: str = '', faculty_id: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    if date:
        cur.execute('INSERT INTO sessions (name, date, subject, faculty_id) VALUES (?, ?, ?, ?)', (name, date, subject, faculty_id))
    else:
        cur.execute('INSERT INTO sessions (name, subject, faculty_id) VALUES (?, ?, ?)', (name, subject, faculty_id))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid

def list_sessions() -> List[Tuple[int,str,str,str,Optional[str]]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, name, date, subject, faculty_id FROM sessions ORDER BY date DESC, id DESC')
    rows = cur.fetchall()
    conn.close()
    return rows

def list_sessions_for_faculty(faculty_id: str) -> List[Tuple[int,str,str,str,Optional[str]]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, name, date, subject, faculty_id FROM sessions WHERE faculty_id = ? ORDER BY date DESC, id DESC', (faculty_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_session(session_id: int) -> Optional[Tuple[int,str,str,str,Optional[str]]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, name, date, subject, faculty_id FROM sessions WHERE id = ?', (session_id,))
    row = cur.fetchone()
    conn.close()
    return row

def mark_session_attendance(session_id: int, user_id: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO session_attendance (session_id, user_id) VALUES (?, ?)', (session_id, user_id))
        conn.commit()
        ok = cur.rowcount > 0
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok

def unmark_session_attendance(session_id: int, user_id: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM session_attendance WHERE session_id = ? AND user_id = ?', (session_id, user_id))
    conn.commit()
    conn.close()

def session_attendance_roster(session_id: int) -> List[Tuple[str, str, str, int]]:
    """Return [(id, name, roll, marked_flag)] for students enrolled under the session's subject and faculty."""
    conn = get_conn()
    cur = conn.cursor()
    # Fetch session subject and faculty_id
    cur.execute('SELECT subject, faculty_id FROM sessions WHERE id = ?', (session_id,))
    sess = cur.fetchone()
    subject = sess[0] if sess else ''
    faculty_id = sess[1] if sess else None
    if subject and faculty_id:
        cur.execute('''
            SELECT s.id, s.name, s.roll,
                   CASE WHEN sa.id IS NULL THEN 0 ELSE 1 END AS marked
            FROM enrollments e
            JOIN users s ON s.id = e.student_id AND s.role='student'
            LEFT JOIN session_attendance sa
                ON sa.user_id = s.id AND sa.session_id = ?
            WHERE e.subject = ? AND e.faculty_id = ?
            ORDER BY s.roll
        ''', (session_id, subject, faculty_id))
    else:
        # Fallback: list all students
        cur.execute('''
            SELECT s.id, s.name, s.roll,
                   CASE WHEN sa.id IS NULL THEN 0 ELSE 1 END AS marked
            FROM users s
            LEFT JOIN session_attendance sa
                ON sa.user_id = s.id AND sa.session_id = ?
            WHERE s.role='student'
            ORDER BY s.roll
        ''', (session_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def upsert_enrollment(student_id: str, faculty_id: str, subject: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO enrollments (student_id, faculty_id, subject)
        VALUES (?, ?, ?)
        ON CONFLICT(student_id, faculty_id, subject) DO NOTHING
    ''', (student_id, faculty_id, subject))
    conn.commit()
    conn.close()

def student_attendance_summary(user_id: str) -> Tuple[int, int]:
    """Return (attended_count, total_sessions)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM sessions')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM session_attendance WHERE user_id = ?', (user_id,))
    attended = cur.fetchone()[0]
    conn.close()
    return attended, total

def seed_sample_data(cur):
    from werkzeug.security import generate_password_hash
    # Create admin (faculty) with requested credentials
    cur.execute('''
        INSERT INTO users (id, name, roll, email, role, password_hash)
        VALUES ('jaga','Admin','','admin@example.com','faculty',?)
        ON CONFLICT(id) DO UPDATE SET password_hash=excluded.password_hash
    ''', (generate_password_hash('212006'),))
    # Create one sample faculty (for demo)
    cur.execute('''
        INSERT INTO users (id, name, roll, email, role, password_hash)
        VALUES ('F001','Faculty Admin','','faculty@example.com','faculty',?)
        ON CONFLICT(id) DO NOTHING
    ''', (generate_password_hash('admin123'),))
    # 25 students
    for i in range(1, 26):
        sid = f"S{i:03d}"
        name = f"Student {i}"
        roll = f"23MID{280 + i:04d}"
        email = f"student{i}@example.com"
        cur.execute('''
            INSERT INTO users (id, name, roll, email, role, password_hash)
            VALUES (?, ?, ?, ?, 'student', ?)
            ON CONFLICT(id) DO NOTHING
        ''', (sid, name, roll, email, generate_password_hash('pass123')))

def ensure_admin_and_defaults(cur):
    from werkzeug.security import generate_password_hash
    # Ensure admin 'jaga' exists with password '212006'
    cur.execute('''
        INSERT INTO users (id, name, roll, email, role, password_hash)
        VALUES ('jaga','Admin','','admin@example.com','faculty',?)
        ON CONFLICT(id) DO UPDATE SET password_hash=excluded.password_hash
    ''', (generate_password_hash('212006'),))
    # Set default password for students with NULL password_hash
    cur.execute("SELECT COUNT(*) FROM users WHERE role='student' AND (password_hash IS NULL OR password_hash='')")
    missing = cur.fetchone()[0]
    if missing:
        cur.execute("UPDATE users SET password_hash=? WHERE role='student' AND (password_hash IS NULL OR password_hash='')",
                    (generate_password_hash('pass123'),))

def ensure_extended_dataset(cur):
    """Ensure there are:
    - 7 faculties (F001..F007), each with one subject
    - 70 students (S001..S070) with rolls 23MID0281..23MID0350
    - Each student enrolled in all 7 subjects under their respective faculty
    - Baseline sessions per subject and some attendance marks for demo
    Idempotent via INSERT OR IGNORE / ON CONFLICT DO NOTHING.
    """
    from werkzeug.security import generate_password_hash
    # Define 7 subjects and faculty mapping
    subjects = [
        'Mathematics', 'Physics', 'Chemistry', 'Biology', 'English', 'Computer Science', 'History'
    ]
    faculties = [f"F{i:03d}" for i in range(1, 8)]
    faculty_names = [
        'Faculty 1','Faculty 2','Faculty 3','Faculty 4','Faculty 5','Faculty 6','Faculty 7'
    ]

    # Create faculties with password 'admin123'
    for fid, fname in zip(faculties, faculty_names):
        cur.execute('''
            INSERT INTO users (id, name, roll, email, role, password_hash)
            VALUES (?, ?, '', ?, 'faculty', ?)
            ON CONFLICT(id) DO NOTHING
        ''', (fid, fname, f"{fid.lower()}@example.com", generate_password_hash('admin123')))

    # Ensure subjects table has 7 subjects
    for s in subjects:
        cur.execute('INSERT OR IGNORE INTO subjects (name) VALUES (?)', (s,))

    # Create 70 students S001..S070 with rolls 23MID0281..23MID0350
    # Keep consistent with any existing S001..S025; this will extend up to S070
    for i, roll_num in enumerate(range(281, 351), start=1):
        sid = f"S{i:03d}"
        name = f"Student {i}"
        roll = f"23MID{roll_num:04d}"
        email = f"student{i}@example.com"
        cur.execute('''
            INSERT INTO users (id, name, roll, email, role, password_hash)
            VALUES (?, ?, ?, ?, 'student', ?)
            ON CONFLICT(id) DO NOTHING
        ''', (sid, name, roll, email, generate_password_hash('pass123')))

    # Map each subject to a faculty (1:1)
    subj_fac = list(zip(subjects, faculties))

    # Enroll every student into all 7 subjects under the mapped faculty
    cur.execute("SELECT id FROM users WHERE role='student' ORDER BY id")
    student_ids = [r[0] for r in cur.fetchall()]
    for student_id in student_ids:
        for subject, fid in subj_fac:
            cur.execute('''
                INSERT INTO enrollments (student_id, faculty_id, subject)
                VALUES (?, ?, ?)
                ON CONFLICT(student_id, faculty_id, subject) DO NOTHING
            ''', (student_id, fid, subject))

    # Create baseline sessions per subject (5 each) for totals
    # Use existing helper list/count via direct SQL
    for subject, fid in subj_fac:
        # Count existing sessions for this mapping
        cur.execute('SELECT COUNT(*) FROM sessions WHERE subject=? AND faculty_id=?', (subject, fid))
        existing = cur.fetchone()[0]
        to_create = max(0, 5 - existing)
        for j in range(to_create):
            cur.execute('INSERT INTO sessions (name, subject, faculty_id) VALUES (?, ?, ?)',
                        (f"Class {existing + j + 1}", subject, fid))

    # Mark some attendance for demonstration: for first 2 sessions of each subject, mark ~50% students
    # Get session ids per subject/faculty
    cur.execute('SELECT id, subject, faculty_id FROM sessions ORDER BY id')
    sessions = cur.fetchall()
    # Build quick map subject->session_ids
    from collections import defaultdict
    sess_map = defaultdict(list)
    for sid, subj, fid in sessions:
        sess_map[(subj, fid)].append(sid)
    # For determinism, mark attendance for every other student in first 2 sessions per subject
    for (subj, fid), sids in sess_map.items():
        for sid in sids[:2]:
            for idx, student_id in enumerate(student_ids):
                if idx % 2 == 0:  # roughly 50%
                    try:
                        cur.execute('INSERT INTO session_attendance (session_id, user_id) VALUES (?, ?)', (sid, student_id))
                    except sqlite3.IntegrityError:
                        pass
