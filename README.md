# Smart Attendance via QR

This is a simple Python-based **Smart Attendance System using QR codes**.  
It supports:
- Generating unique QR codes for users (students/employees) from a CSV.
- Scanning QR codes using a webcam to mark attendance in a local SQLite database.
- Exporting attendance records to CSV.
- A Flask web app with role-based login (student/faculty), browser camera QR scanning, manual marking, student management, and attendance percentage view.

## What's included
- `main.py` — menu-driven CLI to run tasks.
- `qr_generator.py` — generate QR PNG files from a CSV of users.
- `scanner.py` — run webcam scanner to capture and mark attendance automatically.
- `db.py` — database helpers using SQLite (`attendance.db`).
- `sample_users.csv` — example CSV to create users.
- `requirements.txt` — Python packages to install.
- `qrcodes/` — folder created at runtime to store QR images.
- `attendance.db` — created when you initialize the database.

## Web App (Flask) Quick Start
1. Create venv (recommended) and install deps:
   - `pip install -r requirements.txt`
2. Start the web app:
   - `python app.py`
3. Login:
   - Faculty: ID `F001`, password `admin123`.
   - Students: IDs `S001`..`S025`, password `pass123`.
   - These default users are auto-seeded on first run if the database is empty.
4. Faculty flow:
   - Create a session: Faculty Dashboard → New Session.
   - Open the session → click Open Scanner to use your browser camera.
   - Show a student's QR (from their Student Dashboard) to mark attendance.
   - Toggle presence manually per student on the session detail page.
   - Manage Students to add new students or faculty.
5. Student flow:
   - Login → Student Dashboard shows your QR and attendance percentage.

Notes:
- The scanner page uses the `html5-qrcode` browser library via CDN; ensure camera permission is allowed.
- QR payloads are compatible with the CLI/OpenCV scanner.

## Requirements
- Python 3.8+
- VSCode (or any code editor)
- A working webcam
- Install packages:
```
pip install -r requirements.txt
```

## Quick start (step-by-step)
1. Open this folder in VSCode.
2. Create a virtual environment (recommended):
   - Windows: `python -m venv venv` then `.env\Scripts\activate`
   - macOS/Linux: `python3 -m venv venv` then `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Initialize the database and add sample users:
   - Run: `python main.py init_db`
   - Then: `python main.py add_users sample_users.csv`
   - This creates `attendance.db` and stores users.
5. Generate QR codes (PNG files) for users:
   - `python main.py gen_qr`  (QRs will be saved in `qrcodes/` folder)
6. Start the scanner and mark attendance:
   - `python main.py scan`
   - Show a user's QR (on phone or printed) to the webcam. The script will detect & mark attendance.
7. Export attendance to CSV:
   - `python main.py export attendance_export.csv`

## File format for users CSV (`sample_users.csv`)
```
id,name,roll,email
1,Jagadeesh,23MID0283,jagadeesh@example.com
2,Anita,23MID0284,anita@example.com
3,Rahul,23MID0285,rahul@example.com
```

## Notes & troubleshooting
- The scanner uses OpenCV's `QRCodeDetector`. If detection fails often, ensure your webcam has good lighting and the QR is clear.
- If you get errors about missing packages, re-check `pip install -r requirements.txt` inside the activated venv.
- On some platforms, webcam device number may need changing (scanner.py, variable `CAM_INDEX`).

If you want, I can also add a simple Flask web UI later. Enjoy!

