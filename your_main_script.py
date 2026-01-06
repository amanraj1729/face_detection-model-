# your_main_script.py (Final Complete Version)

import os
import cv2
import face_recognition
import threading
import time
from datetime import datetime, timedelta
from imutils import face_utils
import dlib
from scipy.spatial import distance
import numpy as np

from database import (
    get_db, create_database_and_tables,
    sync_enrollment_data, load_known_faces_from_db, mark_attendance
)

# --- CONFIGURATION ---
ENROLLMENT_DIR = "enrollment_images"
# CAMERA_SOURCES = [0]
# --- CONFIGURATION SECTION ---
# This section remains mostly the same.

# List of camera sources.
# For webcams, use integers: 0, 1, 2, ...
# For IP cameras, use the full RTSP or HTTP stream URL in quotes.
CAMERA_SOURCES = [
    0,
    # "rtsp://username:password@192.168.1.101:554/stream1",
    # "http://192.168.1.102:8080/video"
]
RE_ENCODE_INTERVAL_DAYS = 15 #time interval for automatically re-encoding and re-capturing
TIMESTAMP_FILE = "last_sync_timestamp.txt"
EAR_THRESHOLD = 0.2
CONSEC_FRAMES = 2
RECOGNITION_TOLERANCE = 0.4
MAX_PHOTOS_PER_PERSON = 3

# --- STEP 1 & 2: DATABASE SETUP AND PERIODIC SYNC (SELF-LEARNING) ---
print("--- Initializing Database ---")
create_database_and_tables()
db_session = next(get_db())

is_sync_and_capture_day = False
if not os.path.exists(TIMESTAMP_FILE):
    print("No sync timestamp found. Activating 'Sync & Capture' mode for this run.")
    is_sync_and_capture_day = True
else:
    with open(TIMESTAMP_FILE, "r") as f:
        try:
            last_sync_time = datetime.fromisoformat(f.read())
            if datetime.now() - last_sync_time > timedelta(days=RE_ENCODE_INTERVAL_DAYS):
                print(f"Over {RE_ENCODE_INTERVAL_DAYS} days have passed. Activating 'Sync & Capture' mode.")
                is_sync_and_capture_day = True
        except ValueError:
            print("Invalid timestamp format. Activating 'Sync & Capture' mode.")
            is_sync_and_capture_day = True

if is_sync_and_capture_day:
    sync_enrollment_data(db_session, ENROLLMENT_DIR)
    with open(TIMESTAMP_FILE, "w") as f:
        f.write(datetime.now().isoformat())
else:
    print("Normal Day: Database sync not required.")

# --- STEP 3: LOAD FACES INTO MEMORY ---
known_face_encodings, known_face_student_ids, student_details_map = load_known_faces_from_db(db_session)
db_session.close()

# --- STEP 4: DLIB SETUP ---
detector = dlib.get_frontal_face_detector()
if not os.path.exists("shape_predictor_68_face_landmarks.dat"):
    print("Error: 'shape_predictor_68_face_landmarks.dat' not found.")
    exit()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

# --- STEP 5: FINALIZED LIVE RECOGNITION FUNCTION ---
stop_threads = False
def eye_aspect_ratio(eye):
    denom = distance.euclidean(eye[0], eye[3])
    return (distance.euclidean(eye[1], eye[5]) + distance.euclidean(eye[2], eye[4])) / (2.0 * denom) if denom != 0 else 0.3

def process_camera_feed(camera_source, camera_id, is_capture_day): # Added is_capture_day flag
    global stop_threads
    video_capture = cv2.VideoCapture(camera_source)
    if not video_capture.isOpened(): return
    print(f"🎥 [Camera {camera_id}] Starting feed... | Capture Mode: {'ON' if is_capture_day else 'OFF'}")
    db = next(get_db())
    blink_counter = {}

    while not stop_threads:
        ret, frame = video_capture.read()
        if not ret: break
        
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        
        face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        rects = detector(gray, 0)
        
        if len(face_locations) == len(rects):
            for face_location, face_encoding, rect in zip(face_locations, face_encodings, rects):
                name = "Unknown"
                student_id = None
                
                if known_face_encodings:
                    matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE)
                    if True in matches:
                        best_match_index = np.argmin(face_recognition.face_distance(known_face_encodings, face_encoding))
                        if matches[best_match_index]:
                            student_id = known_face_student_ids[best_match_index]
                            name = student_details_map.get(student_id, {}).get("name", "Unknown")
                
                shape = predictor(gray, rect)
                shape_np = face_utils.shape_to_np(shape)
                ear = (eye_aspect_ratio(shape_np[lStart:lEnd]) + eye_aspect_ratio(shape_np[rStart:rEnd])) / 2.0
                
                if ear < EAR_THRESHOLD:
                    blink_counter[name] = blink_counter.get(name, 0) + 1
                else:
                    if blink_counter.get(name, 0) >= CONSEC_FRAMES:
                        if student_id and mark_attendance(db, student_id, camera_id):
                            print(f"✅ [Camera {camera_id}] Attendance marked for {name}")
                            
                            # Only capture photos on a "Sync & Capture Day"
                            if is_capture_day:
                                student_info = student_details_map.get(student_id)
                                if student_info:
                                    person_dir = os.path.join(ENROLLMENT_DIR, str(student_info['school_id']), student_info['name'])
                                    os.makedirs(person_dir, exist_ok=True)
                                    if len(os.listdir(person_dir)) < MAX_PHOTOS_PER_PERSON:
                                        filename = f"{student_info['name']}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
                                        cv2.imwrite(os.path.join(person_dir, filename), frame)
                                        print(f"📸 [Capture Mode ON] Saved new image for {name}.")
                    blink_counter[name] = 0

                top, right, bottom, left = face_location
                top *= 2; right *= 2; bottom *= 2; left *= 2
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow(f"Camera {camera_id} Feed", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            stop_threads = True
            break
    
    video_capture.release()
    db.close()

# --- STEP 6: MAIN THREAD LAUNCHER ---
# if __name__ == "__main__":
#     if not known_face_encodings:
#         print("⚠️ No faces loaded from database. Please add images to the 'enrollment_images' folder.")
    
#     threads = []
#     for i, source in enumerate(CAMERA_SOURCES):
#         # Pass the is_sync_and_capture_day flag to each thread
#         thread = threading.Thread(target=process_camera_feed, args=(source, i, is_sync_and_capture_day))
#         threads.append(thread)
#         thread.start()
#         time.sleep(1)
    
#     for thread in threads:
#         thread.join()
    
#     cv2.destroyAllWindows()
#     print("All processing stopped.")




# In your_main_script.py

# --- STEP 6: MAIN THREAD LAUNCHER (with Smoother Exit) ---
if __name__ == "__main__":
    if not known_face_encodings:
        print("⚠️ No faces loaded from database. Please add images to the 'enrollment_images' folder.")
    
    threads = []
    for i, source in enumerate(CAMERA_SOURCES):
        # Pass the is_sync_and_capture_day flag to each thread
        thread = threading.Thread(target=process_camera_feed, args=(source, i, is_sync_and_capture_day))
        threads.append(thread)
        thread.start()
        # No need for a sleep here, threads will start up
    
    # Wait for all threads to complete after 'q' is pressed
    for thread in threads:
        thread.join()
    
    # This final call ensures all OpenCV windows are closed properly
    cv2.destroyAllWindows()
    print("All processing stopped. Exiting.")