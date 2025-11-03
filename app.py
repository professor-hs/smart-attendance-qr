from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, flash, send_file
from werkzeug.security import check_password_hash, generate_password_hash
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
USE_SHEETS = os.environ.get('SHEETS_ENABLED', '0') == '1'
if USE_SHEETS:
    from sheets_db import (
        init_db,
        get_user_auth,
        get_user_by_roll,
        upsert_user_with_auth,
        list_students,
        create_session,
        list_sessions,
        get_session,
        session_attendance_roster,
        mark_session_attendance,
        unmark_session_attendance,
        student_attendance_summary,
    )
else:
    from db import (
        init_db,
        get_user_auth,
        get_user_by_roll,
        upsert_user_with_auth,
        list_students,
        create_session,
        list_sessions,
        list_sessions_for_faculty,
        get_session,
        session_attendance_roster,
        mark_session_attendance,
        unmark_session_attendance,
        student_attendance_summary,
        set_user_password,
        delete_all_sessions,
        delete_session,
        reassign_session_faculty,
        student_subject_summary,
        list_faculty_subjects,
        count_sessions_for,
    )
from qr_generator import generate_qr_for_user

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change')

# Ensure folders
os.makedirs('qrcodes', exist_ok=True)


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    row = get_user_auth(uid)
    return row

def is_admin() -> bool:
    u = current_user()
    return bool(u and u[0] == 'jaga')


def require_role(role):
    def decorator(fn):
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for('login'))
            # Admin bypasses role restrictions
            if role and user[4] != role and not is_admin():
                return redirect(url_for('index'))
            return fn(*args, **kwargs)
        wrapped.__name__ = fn.__name__
        return wrapped
    return decorator


@app.route('/')
def index():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if user[4] == 'faculty':
        return redirect(url_for('faculty_dashboard'))
    return redirect(url_for('student_dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    init_db()
    error = None
    if request.method == 'POST':
        user_identifier = request.form.get('user_id', '').strip()
        password = request.form.get('password', '')
        row = None
        # 1) Admin shortcut: username 'jaga'
        if user_identifier.lower() == 'jaga':
            row = get_user_auth('jaga')
        # 2) Faculty by employee ID (stored as id)
        if row is None:
            candidate = get_user_auth(user_identifier)
            if candidate and candidate[4] == 'faculty':
                row = candidate
        # 3) Student by registration number (roll)
        if row is None:
            candidate = get_user_by_roll(user_identifier)
            if candidate and candidate[4] == 'student':
                row = candidate

        if row:
            pw_hash = row[5]
            if pw_hash and check_password_hash(pw_hash, password):
                session['user_id'] = row[0]
                role = row[4]
                return redirect(url_for('faculty_dashboard' if role == 'faculty' else 'student_dashboard'))
        error = 'Invalid username/roll or password'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/student')
@require_role('student')
def student_dashboard():
    user = current_user()
    uid, name, roll, email, role, _ = user
    attended, total = student_attendance_summary(uid)
    percentage = (attended / total * 100.0) if total > 0 else 0.0
    # Warn on low attendance (<75%) once per session
    try:
        if percentage < 75 and not session.get('warned_low_att'):
            flash(f"Warning: Your attendance is {percentage:.1f}% which is below 75%", 'error')
            session['warned_low_att'] = True
    except Exception:
        pass
    summaries = student_subject_summary(uid)
    # Ensure QR exists for this student
    payload = f"{{'id':'{uid}','name':'{name}','roll':'{roll}','email':'{email}'}}"
    qr_path = os.path.join('qrcodes', f'{uid}.png')
    if not os.path.exists(qr_path):
        generate_qr_for_user(uid, payload)
    return render_template('student_dashboard.html', user={"id": uid, "name": name, "roll": roll, "email": email},
                           attended=attended, total=total, percentage=percentage, summaries=summaries)


@app.route('/student/subjects')
@require_role('student')
def student_subjects():
    u = current_user()
    summaries = student_subject_summary(u[0])
    return render_template('student_subjects.html', summaries=summaries)


@app.route('/student/report.pdf')
@require_role('student')
def student_report_pdf():
    u = current_user()
    uid, name = u[0], u[1]
    overall_attended, overall_total = student_attendance_summary(uid)
    summaries = student_subject_summary(uid)
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(40, y, 'Attendance Report')
    pdf.setFont('Helvetica', 10)
    y -= 18
    pdf.drawString(40, y, f'Name: {name}   ID: {uid}')
    y -= 16
    pct = (overall_attended / overall_total * 100.0) if overall_total > 0 else 0.0
    pdf.drawString(40, y, f'Overall: {overall_attended}/{overall_total} ({pct:.1f}%)')
    y -= 24
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(40, y, 'Subject')
    pdf.drawString(300, y, 'Attended/Total')
    pdf.drawString(460, y, 'Percent')
    y -= 14
    pdf.setFont('Helvetica', 10)
    for subject, attended, total, percent in summaries:
        if y < 60:
            pdf.showPage()
            y = height - 50
            pdf.setFont('Helvetica-Bold', 11)
            pdf.drawString(40, y, 'Subject')
            pdf.drawString(300, y, 'Attended/Total')
            pdf.drawString(460, y, 'Percent')
            y -= 14
            pdf.setFont('Helvetica', 10)
        pdf.drawString(40, y, str(subject))
        pdf.drawString(300, y, f'{attended}/{total}')
        pdf.drawString(460, y, f'{percent:.1f}%')
        y -= 14
    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'{uid}_attendance_report.pdf')


@app.route('/student/reset-password', methods=['GET','POST'])
@require_role('student')
def student_reset_password():
    user = current_user()
    uid = user[0]
    error = None
    success = None
    if request.method == 'POST':
        current_pw = request.form.get('current_password','')
        new_pw = request.form.get('new_password','')
        confirm_pw = request.form.get('confirm_password','')
        # Verify current
        row = get_user_auth(uid)
        if not row or not row[5] or not check_password_hash(row[5], current_pw):
            error = 'Current password is incorrect'
        elif len(new_pw) < 6:
            error = 'New password must be at least 6 characters'
        elif new_pw != confirm_pw:
            error = 'New password and confirm do not match'
        else:
            set_user_password(uid, generate_password_hash(new_pw))
            flash('Password updated successfully','success')
            return redirect(url_for('student_dashboard'))
    return render_template('student_reset_password.html', error=error)


@app.route('/qrcodes/<path:filename>')
@require_role('student')
def qrcodes_static(filename):
    return send_from_directory('qrcodes', filename)


@app.route('/faculty')
@require_role('faculty')
def faculty_dashboard():
    u = current_user()
    faculty_id = u[0]
    sessions = list_sessions_for_faculty(faculty_id)
    return render_template('faculty_dashboard.html', sessions=sessions)


@app.route('/faculty/session/new', methods=['GET'])
@require_role('faculty')
def session_new():
    u = current_user()
    fid = u[0]
    subjects = list_faculty_subjects(fid)
    # One-click: auto-create using the faculty's subject (assumes one per faculty)
    subject = (subjects[0] if subjects else '').strip()
    next_num = count_sessions_for(fid, subject) + 1 if subject else 1
    name = f"Class {next_num}"
    sid = create_session(name, subject=subject, faculty_id=fid)
    return redirect(url_for('session_detail', session_id=sid))


@app.route('/faculty/session/<int:session_id>')
@require_role('faculty')
def session_detail(session_id: int):
    sess = get_session(session_id)
    if not sess:
        return redirect(url_for('faculty_dashboard'))
    # Enforce per-faculty visibility (admin bypass)
    u = current_user()
    if not is_admin() and sess[4] and sess[4] != u[0]:
        return redirect(url_for('faculty_dashboard'))
    roster = session_attendance_roster(session_id)
    return render_template('session_detail.html', sess=sess, roster=roster)


@app.route('/faculty/session/<int:session_id>/delete', methods=['POST'])
@require_role('faculty')
def faculty_delete_session(session_id: int):
    sess = get_session(session_id)
    if not sess:
        return redirect(url_for('faculty_dashboard'))
    u = current_user()
    # Only owning faculty or admin can delete
    if not is_admin() and sess[4] and sess[4] != u[0]:
        return redirect(url_for('faculty_dashboard'))
    delete_session(session_id)
    flash('Class deleted.','success')
    return redirect(url_for('faculty_dashboard'))


# Admin-only routes
@app.route('/admin/sessions')
@require_role(None)
def admin_sessions():
    if not is_admin():
        return redirect(url_for('faculty_dashboard'))
    sessions = list_sessions()
    return render_template('admin_sessions.html', sessions=sessions)


@app.route('/admin/sessions/delete_all', methods=['POST'])
@require_role(None)
def admin_delete_all_sessions():
    if not is_admin():
        return redirect(url_for('faculty_dashboard'))
    delete_all_sessions()
    flash('All classes deleted.','success')
    return redirect(url_for('admin_sessions'))


@app.route('/admin/sessions/<int:session_id>/reassign', methods=['POST'])
@require_role(None)
def admin_reassign_session(session_id: int):
    if not is_admin():
        return redirect(url_for('faculty_dashboard'))
    new_faculty = request.form.get('faculty_id','').strip()
    if new_faculty:
        reassign_session_faculty(session_id, new_faculty)
        flash('Session reassigned.','success')
    return redirect(url_for('admin_sessions'))


@app.route('/admin/users')
@require_role(None)
def admin_users():
    if not is_admin():
        return redirect(url_for('index'))
    # list all faculty and students
    fac = [u for u in list_students() if False]  # placeholder to keep import usage consistent
    # Build separate queries using get_user_auth + list_students existing
    # We will reuse the DB directly via helper list_students and a small inline query
    from db import get_conn
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email FROM users WHERE role='faculty' ORDER BY id")
    faculties = cur.fetchall()
    conn.close()
    students = list_students()
    return render_template('admin_users.html', faculties=faculties, students=students)


@app.route('/faculty/session/<int:session_id>/mark', methods=['POST'])
@require_role('faculty')
def session_mark(session_id: int):
    user_id = request.form.get('user_id', '').strip()
    if user_id:
        mark_session_attendance(session_id, user_id)
    return redirect(url_for('session_detail', session_id=session_id))


@app.route('/faculty/session/<int:session_id>/toggle/<user_id>', methods=['POST'])
@require_role('faculty')
def session_toggle(session_id: int, user_id: str):
    # Toggle mark
    if not mark_session_attendance(session_id, user_id):
        unmark_session_attendance(session_id, user_id)
    return redirect(url_for('session_detail', session_id=session_id))


@app.route('/faculty/students', methods=['GET', 'POST'])
@require_role('faculty')
def students_page():
    if request.method == 'POST':
        user_id = request.form.get('id', '').strip()
        name = request.form.get('name', '').strip()
        roll = request.form.get('roll', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'student')
        password = request.form.get('password', '').strip() or 'pass123'
        upsert_user_with_auth(user_id, name, roll, email, role, generate_password_hash(password))
        flash('User saved', 'success')
        return redirect(url_for('students_page'))
    students = list_students()
    return render_template('students.html', students=students)


# QR scan page for faculty using camera
@app.route('/faculty/scan/<int:session_id>')
@require_role('faculty')
def scan_page(session_id: int):
    sess = get_session(session_id)
    if not sess:
        return redirect(url_for('faculty_dashboard'))
    return render_template('scan.html', sess=sess)


def extract_id_from_payload(payload: str):
    try:
        token = "'id':'"
        start = payload.index(token) + len(token)
        end = payload.index("'", start)
        return payload[start:end]
    except Exception:
        return None


@app.post('/api/scan_mark')
@require_role('faculty')
def api_scan_mark():
    data = request.get_json(silent=True) or {}
    payload = data.get('payload', '')
    session_id = data.get('session_id')
    if not payload or not session_id:
        return jsonify({'ok': False, 'error': 'missing'}), 400
    user_id = extract_id_from_payload(payload)
    if not user_id:
        return jsonify({'ok': False, 'error': 'bad_payload'}), 400
    ok = mark_session_attendance(int(session_id), user_id)
    return jsonify({'ok': True, 'marked': ok, 'user_id': user_id})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
