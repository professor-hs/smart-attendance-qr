import cv2
from db import get_user, mark_attendance
import time

CAM_INDEX = 0  # change if your webcam is a different index

def extract_id_from_payload(payload: str):
    # payload format: we created a string like: {'id':'1','name':'Jagadeesh',...}
    # We'll do a simple parse to extract id between "'id':'" and "'"
    try:
        token = "'id':'"
        start = payload.index(token) + len(token)
        end = payload.index("'", start)
        return payload[start:end]
    except Exception:
        return None

def run_scanner():
    detector = cv2.QRCodeDetector()
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        print('ERROR: Could not open webcam. Try changing CAM_INDEX in scanner.py')
        return
    last_seen = {}
    print('Scanner running. Press q to quit.')
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        data, points, _ = detector.detectAndDecode(frame)
        if data:
            user_id = extract_id_from_payload(data)
            if user_id:
                # debounce: don't re-mark the same user more than once in 5 seconds in UI
                now = time.time()
                if user_id not in last_seen or now - last_seen[user_id] > 5:
                    last_seen[user_id] = now
                    user = get_user(user_id)
                    if user:
                        inserted = mark_attendance(user_id)
                        name = user[1]
                        if inserted:
                            print(f'Attendance marked for {name} (id={user_id})')
                        else:
                            print(f'Already marked today: {name} (id={user_id})')
                        # display on frame by drawing text
                        cv2.putText(frame, f"{name} -> {'Marked' if inserted else 'Already'}", (50,50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                    else:
                        print('Unknown user id scanned:', user_id)
                        cv2.putText(frame, 'Unknown user', (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
        cv2.imshow('QR Scanner - press q to quit', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    run_scanner()
