import sys, csv, os
from db import init_db, add_users_from_list, export_attendance_csv, get_user_auth, get_user_by_roll, upsert_user_with_auth, upsert_enrollment
from werkzeug.security import generate_password_hash
from qr_generator import generate_qr_from_db
from scanner import run_scanner

def cmd_init_db():
    init_db()
    print('Database initialized (attendance.db)')

def cmd_add_users(csv_path):
    if not os.path.exists(csv_path):
        print('CSV not found:', csv_path); return
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            uid = r.get('id') or r.get('ID') or r.get('user_id')
            name = r.get('name') or ''
            roll = r.get('roll') or ''
            email = r.get('email') or ''
            rows.append((uid, name, roll, email))
    add_users_from_list(rows)
    print(f'Added/updated {len(rows)} users from', csv_path)

def cmd_gen_qr():
    created = generate_qr_from_db()
    print('Generated', len(created), 'QR images in qrcodes/')

def cmd_scan():
    run_scanner()

def cmd_export(out_path):
    export_attendance_csv(out_path)
    print('Exported attendance to', out_path)

def cmd_apply_credentials(csv_path):
    if not os.path.exists(csv_path):
        print('CSV not found:', csv_path); return
    init_db()
    updated = 0
    created = 0
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            username = (r.get('username') or '').strip()
            password = (r.get('password') or '').strip()
            role = (r.get('role') or '').strip().lower()
            if not username or not password or not role:
                continue
            pw_hash = generate_password_hash(password)
            if role == 'faculty':
                existing = get_user_auth(username)
                name = r.get('description') or username
                if existing:
                    upsert_user_with_auth(username, existing[1] or name, existing[2] or '', existing[3] or '', 'faculty', pw_hash)
                    updated += 1
                else:
                    upsert_user_with_auth(username, name, '', '', 'faculty', pw_hash)
                    created += 1
            elif role == 'student':
                # username is the registration number (roll)
                existing = get_user_by_roll(username)
                if existing:
                    upsert_user_with_auth(existing[0], existing[1], existing[2], existing[3], 'student', pw_hash)
                    updated += 1
                else:
                    # create with id same as roll
                    upsert_user_with_auth(username, r.get('description') or username, username, '', 'student', pw_hash)
                    created += 1
    print(f'Credentials applied. Updated={updated}, Created={created}')

def cmd_apply_enrollments(csv_path):
    if not os.path.exists(csv_path):
        print('CSV not found:', csv_path); return
    init_db()
    applied = 0
    skipped = 0
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            subject = (r.get('subject') or '').strip()
            faculty_id = (r.get('faculty_id') or '').strip()
            student_roll = (r.get('student_roll') or '').strip()
            if not subject or not faculty_id or not student_roll:
                skipped += 1; continue
            fac = get_user_auth(faculty_id)
            stu = get_user_by_roll(student_roll)
            if not fac or fac[4] != 'faculty' or not stu:
                skipped += 1; continue
            upsert_enrollment(stu[0], faculty_id, subject)
            applied += 1
    print(f'Enrollments applied. Applied={applied}, Skipped={skipped}')

def print_help():
    print('Usage: python main.py <command> [args]')
    print('Commands:')
    print('  init_db                Initialize the SQLite database')
    print('  add_users <csv_path>   Add users from CSV (id,name,roll,email)')
    print('  gen_qr                 Generate QR PNG files for users from DB')
    print('  scan                   Start webcam scanner to mark attendance')
    print('  export <out.csv>       Export attendance records to CSV')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_help(); sys.exit(0)
    cmd = sys.argv[1]
    if cmd == 'init_db':
        cmd_init_db()
    elif cmd == 'add_users' and len(sys.argv) >= 3:
        cmd_add_users(sys.argv[2])
    elif cmd == 'gen_qr':
        cmd_gen_qr()
    elif cmd == 'scan':
        cmd_scan()
    elif cmd == 'export' and len(sys.argv) >= 3:
        cmd_export(sys.argv[2])
    elif cmd == 'apply_credentials' and len(sys.argv) >= 3:
        cmd_apply_credentials(sys.argv[2])
    elif cmd == 'apply_enrollments' and len(sys.argv) >= 3:
        cmd_apply_enrollments(sys.argv[2])
    else:
        print_help()
