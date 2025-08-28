
# #updated api code for deployment 14th aug 2025

# # api.py (Final Production-Ready Version)

# import uvicorn
# from fastapi import FastAPI, Form, UploadFile, File, HTTPException
# from contextlib import asynccontextmanager
# from datetime import date, datetime, timedelta
# import os
# import cv2
# import numpy as np
# import face_recognition
# import boto3
# import shutil

# # Import all necessary components from your database file
# from database import (
#     get_db, School, Student, AttendanceLog,
#     sync_enrollment_data, load_known_faces_from_db, mark_attendance
# )

# # --- CONFIGURATION ---
# RECOGNITION_TOLERANCE = 0.4
# S3_BUCKET_NAME = "myleadingcampus-student-photos" # Your S3 bucket name
# RE_ENCODE_INTERVAL_DAYS = 15
# TIMESTAMP_FILE = "last_sync_timestamp.txt"
# MAX_PHOTOS_PER_PERSON = 3
# TEMP_DIR = "/tmp/api_uploads"

# os.makedirs(TEMP_DIR, exist_ok=True)

# # --- GLOBAL VARIABLES & LIFESPAN EVENT (The new, correct way) ---
# # This dictionary will hold our application's state
# app_state = {
#     "known_face_encodings": [],
#     "known_face_student_ids": [],
#     "student_details_map": {},
#     "is_capture_day": False
# }

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Handles application startup and shutdown events."""
#     # --- STARTUP LOGIC ---
#     print("API is starting up...")
#     db = next(get_db())
    
#     if not os.path.exists(TIMESTAMP_FILE) or (datetime.now() - datetime.fromisoformat(open(TIMESTAMP_FILE).read()) > timedelta(days=RE_ENCODE_INTERVAL_DAYS)):
#         print("Activating 'Sync & Capture' mode for this session.")
#         app_state["is_capture_day"] = True
#         sync_enrollment_data(db)
#         with open(TIMESTAMP_FILE, "w") as f:
#             f.write(datetime.now().isoformat())
#     else:
#         print("Normal Day: Database sync not required.")
    
#     # Load faces into the app_state dictionary
#     (
#         app_state["known_face_encodings"],
#         app_state["known_face_student_ids"],
#         app_state["student_details_map"],
#     ) = load_known_faces_from_db(db)
    
#     db.close()
#     print("Face data loaded. API is ready.")
    
#     yield # The API is now running
    
#     # --- SHUTDOWN LOGIC (if any) ---
#     print("API is shutting down.")

# # Assign the lifespan event handler to the FastAPI app
# app = FastAPI(title="MyLeading campus Attendance API", lifespan=lifespan)

# # --- S3 HELPER ---
# def upload_to_s3(file_path, object_name):
#     s3_client = boto3.client('s3')
#     try:
#         s3_client.upload_file(file_path, S3_BUCKET_NAME, object_name)
#         return True
#     except Exception as e:
#         print(f"Error uploading to S3: {e}")
#         return False

# # --- FULLY CONNECTED API ENDPOINTS ---

# @app.post("/students/enroll")
# async def enroll_student(school_id: int = Form(...), student_name: str = Form(...), image: UploadFile = File(...)):
#     """Enrolls a student by uploading their photo to S3 and re-syncing the database."""
#     s3_object_name = f"{school_id}/{student_name}/{image.filename}"
#     temp_file_path = os.path.join(TEMP_DIR, image.filename)

#     with open(temp_file_path, "wb") as buffer:
#         shutil.copyfileobj(image.file, buffer)
    
#     if upload_to_s3(temp_file_path, s3_object_name):
#         db = next(get_db())
#         sync_enrollment_data(db)
#         # Reload faces into memory after sync
#         (
#             app_state["known_face_encodings"],
#             app_state["known_face_student_ids"],
#             app_state["student_details_map"],
#         ) = load_known_faces_from_db(db)
#         db.close()
#         os.remove(temp_file_path)
#         return {"status": "success", "message": f"Student '{student_name}' enrolled."}
#     else:
#         os.remove(temp_file_path)
#         raise HTTPException(status_code=500, detail="Could not upload photo to S3.")

# @app.post("/attendance/mark")
# async def mark_attendance_endpoint(camera_id: str = Form(...), image: UploadFile = File(...)):
#     """Receives an image, recognizes faces, marks attendance, and captures photos on sync days."""
#     contents = await image.read()
#     nparr = np.frombuffer(contents, np.uint8)
#     frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb_frame)
#     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#     recognized_students = []
#     for face_encoding in face_encodings:
#         if app_state["known_face_encodings"]:
#             matches = face_recognition.compare_faces(app_state["known_face_encodings"], face_encoding, tolerance=RECOGNITION_TOLERANCE)
#             if True in matches:
#                 best_match_index = np.argmin(face_recognition.face_distance(app_state["known_face_encodings"], face_encoding))
#                 if matches[best_match_index]:
#                     student_id = app_state["known_face_student_ids"][best_match_index]
#                     student_info = app_state["student_details_map"].get(student_id)
#                     name = student_info.get("name", "Unknown") if student_info else "Unknown"

#                     db = next(get_db())
#                     is_newly_marked = mark_attendance(db, student_id, camera_id)
#                     db.close()

#                     if is_newly_marked:
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "marked"})
#                         # Self-learning photo capture logic
#                         if app_state["is_capture_day"] and student_info:
#                             filename = f"{name}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
#                             s3_object_name = f"{student_info['school_id']}/{name}/{filename}"
#                             temp_file_path = os.path.join(TEMP_DIR, filename)
#                             cv2.imwrite(temp_file_path, frame)
#                             if upload_to_s3(temp_file_path, s3_object_name):
#                                 print(f"📸 [Capture Mode ON] Saved new image for {name} to S3.")
#                             os.remove(temp_file_path)
#                     else:
#                         # This was the missing part: add the student to the response even if already marked.
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "already_marked"})

#     return {"recognized_students": recognized_students}

# # ... (GET endpoints for reports and schools are unchanged and correct) ...

# if __name__ == "__main__":
#     uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

















# api.py (Final S3 Version)

# import uvicorn
# from fastapi import FastAPI, Form, UploadFile, File, HTTPException
# from datetime import date, datetime, timedelta
# import os
# import cv2
# import numpy as np
# import face_recognition
# import boto3
# from botocore.exceptions import NoCredentialsError
# import shutil

# # Import all necessary components from your database file
# from database import (
#     get_db, School, Student, AttendanceLog,
#     sync_enrollment_data, load_known_faces_from_db, mark_attendance
# )

# # --- CONFIGURATION & API SETUP ---
# RECOGNITION_TOLERANCE = 0.4
# S3_BUCKET_NAME = "myleadingcampus-student-photos" # Change to your bucket name
# # S3_BUCKET_NAME = "enrollment_images" # Change to your bucket name
# RE_ENCODE_INTERVAL_DAYS = 15
# TIMESTAMP_FILE = "last_sync_timestamp.txt"
# MAX_PHOTOS_PER_PERSON = 3
# TEMP_DIR = "/tmp/api_uploads" # Use a temporary directory for file operations

# os.makedirs(TEMP_DIR, exist_ok=True)
# app = FastAPI(title="MyLeading campus Attendance API")

# # --- GLOBAL VARIABLES & STARTUP EVENT ---
# known_face_encodings = []
# known_face_student_ids = []
# student_details_map = {}
# is_capture_day = False # Flag for self-learning photo capture

# @app.on_event("startup")
# def startup_event():
#     """On startup, check sync interval, sync if needed, and load faces."""
#     global is_capture_day
#     db = next(get_db())
    
#     if not os.path.exists(TIMESTAMP_FILE) or (datetime.now() - datetime.fromisoformat(open(TIMESTAMP_FILE).read()) > timedelta(days=RE_ENCODE_INTERVAL_DAYS)):
#         print("Activating 'Sync & Capture' mode for this session.")
#         is_capture_day = True
#         sync_enrollment_data(db)
#         with open(TIMESTAMP_FILE, "w") as f:
#             f.write(datetime.now().isoformat())
#     else:
#         print("Normal Day: Database sync not required.")
    
#     load_faces_into_memory(db)
#     db.close()

# def load_faces_into_memory(db_session):
#     """Helper to load/reload faces into global variables."""
#     global known_face_encodings, known_face_student_ids, student_details_map
#     known_face_encodings, known_face_student_ids, student_details_map = load_known_faces_from_db(db_session)

# # --- S3 HELPER ---
# def upload_to_s3(file_path, object_name):
#     s3_client = boto3.client('s3')
#     try:
#         s3_client.upload_file(file_path, S3_BUCKET_NAME, object_name)
#         return True
#     except Exception as e:
#         print(f"Error uploading to S3: {e}")
#         return False

# # --- FULLY CONNECTED API ENDPOINTS ---

# @app.post("/students/enroll")
# async def enroll_student(school_id: int = Form(...), student_name: str = Form(...), image: UploadFile = File(...)):
#     """Enrolls a student by uploading their photo to S3 and re-syncing the database."""
#     s3_object_name = f"{school_id}/{student_name}/{image.filename}"
#     temp_file_path = os.path.join(TEMP_DIR, image.filename)

#     with open(temp_file_path, "wb") as buffer:
#         shutil.copyfileobj(image.file, buffer)
    
#     if upload_to_s3(temp_file_path, s3_object_name):
#         db = next(get_db())
#         sync_enrollment_data(db) # Re-sync to enroll the new student from S3
#         load_faces_into_memory(db) # Reload faces into memory
#         db.close()
#         os.remove(temp_file_path)
#         return {"status": "success", "message": f"Student '{student_name}' enrolled."}
#     else:
#         os.remove(temp_file_path)
#         raise HTTPException(status_code=500, detail="Could not upload photo to S3.")

# @app.post("/attendance/mark")
# async def mark_attendance_endpoint(camera_id: str = Form(...), image: UploadFile = File(...)):
#     """Receives an image, recognizes faces, and marks attendance. Captures photos on sync days."""
#     contents = await image.read()
#     nparr = np.frombuffer(contents, np.uint8)
#     frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb_frame)
#     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#     recognized_students = []
#     for face_encoding in face_encodings:
#         if known_face_encodings:
#             matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE)
#             if True in matches:
#                 best_match_index = np.argmin(face_recognition.face_distance(known_face_encodings, face_encoding))
#                 if matches[best_match_index]:
#                     student_id = known_face_student_ids[best_match_index]
#                     db = next(get_db())
#                     if mark_attendance(db, student_id, camera_id):
#                         student_info = student_details_map.get(student_id)
#                         name = student_info.get("name", "Unknown")
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "marked"})

#                         # Self-learning photo capture logic
#                         if is_capture_day and student_info:
#                             filename = f"{name}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
#                             s3_object_name = f"{student_info['school_id']}/{name}/{filename}"
#                             temp_file_path = os.path.join(TEMP_DIR, filename)
#                             cv2.imwrite(temp_file_path, frame)
#                             if upload_to_s3(temp_file_path, s3_object_name):
#                                 print(f"📸 [Capture Mode ON] Saved new image for {name} to S3.")
#                             os.remove(temp_file_path)
#                     db.close()

#     return {"recognized_students": recognized_students}

# # ... (GET endpoints for reports and schools are unchanged) ...
# @app.get("/schools/")
# def get_all_schools():
#     db = next(get_db())
#     schools = db.query(School).all()
#     db.close()
#     return [{"id": school.id, "name": school.name} for school in schools]

# @app.get("/schools/{school_id}/students/")
# def get_students_for_school(school_id: int):
#     db = next(get_db())
#     students = db.query(Student).filter(Student.school_id == school_id).all()
#     db.close()
#     if not students:
#         raise HTTPException(status_code=404, detail="No students found for this school.")
#     return [{"id": student.id, "name": student.name} for student in students]

# @app.get("/attendance/report/")
# def get_attendance_report(school_id: int, report_date: date):
#     db = next(get_db())
#     report_data = []
#     attendance_records = db.query(AttendanceLog).join(Student).filter(Student.school_id == school_id, AttendanceLog.attendance_date == report_date).all()
#     for rec in attendance_records:
#         student_name = student_details_map.get(rec.student_id, {}).get("name", "N/A")
#         report_data.append({"student_id": rec.student_id, "name": student_name, "first_seen": rec.first_seen_timestamp.strftime("%H:%M:%S")})
#     db.close()
#     return {"school_id": school_id, "date": report_date, "attendees": report_data}


# if __name__ == "__main__":
#     uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)





















































































# # api.py
# import uvicorn
# from fastapi import FastAPI, Form, UploadFile, File, HTTPException
# from datetime import date
# import os
# import cv2
# import numpy as np
# import face_recognition

# # Import our database functions and classes
# from database import (
#     get_db,
#     sync_enrollment_data,
#     load_known_faces_from_db,
#     mark_attendance
# )

# # --- CONFIGURATION ---
# ENROLLMENT_DIR = "enrollment_images"
# RECOGNITION_TOLERANCE = 0.4

# # --- API SETUP ---
# app = FastAPI(
#     title="MyLeading campus Attendance API",
#     description="API for managing school attendance via face recognition."
# )

# # --- GLOBAL VARIABLES to hold face data in memory ---
# # These will be loaded once when the API starts
# known_face_encodings = []
# known_face_student_ids = []
# student_details_map = {}

# @app.on_event("startup")
# def load_data_on_startup():
#     """This function runs when the API server starts up."""
#     global known_face_encodings, known_face_student_ids, student_details_map
#     print("API is starting up. Loading known faces from the database...")
#     db = next(get_db())
#     known_face_encodings, known_face_student_ids, student_details_map = load_known_faces_from_db(db)
#     db.close()
#     print("Face data loaded successfully. API is ready.")

# # --- API ENDPOINTS ---

# @app.post("/students/enroll")
# async def enroll_student(
#     school_id: int = Form(...), 
#     student_name: str = Form(...), 
#     image: UploadFile = File(...)
# ):
#     """
#     Enrolls a new student. This saves their photo and syncs the database.
#     """
#     # 1. Create the necessary directory path
#     student_dir = os.path.join(ENROLLMENT_DIR, str(school_id), student_name)
#     os.makedirs(student_dir, exist_ok=True)
    
#     # 2. Save the uploaded image file
#     file_path = os.path.join(student_dir, image.filename)
#     with open(file_path, "wb") as buffer:
#         buffer.write(await image.read())
    
#     # 3. Run the database sync to process the new student/photo
#     print(f"New photo saved for {student_name}. Running database sync...")
#     db = next(get_db())
#     sync_enrollment_data(db, ENROLLMENT_DIR)
#     db.close()
    
#     # 4. Reload the face data into memory
#     # NOTE: In a production system, this would be handled more efficiently.
#     # For now, we'll call the startup function again to reload.
#     load_data_on_startup()
    
#     return {"status": "success", "message": f"Student '{student_name}' for school {school_id} enrolled successfully."}

# @app.post("/attendance/mark")
# async def mark_attendance_endpoint(
#     camera_id: str = Form(...), 
#     image: UploadFile = File(...)
# ):
#     """
#     Receives an image from a camera, recognizes faces, and marks attendance.
#     NOTE: Liveness detection is not performed here as it requires multiple frames.
#     """
#     # 1. Read the uploaded image into a format OpenCV can use
#     contents = await image.read()
#     nparr = np.frombuffer(contents, np.uint8)
#     frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#     # 2. Run face recognition (without the dlib part for simplicity in the API)
#     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb_frame)
#     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#     recognized_students = []

#     for face_encoding in face_encodings:
#         if known_face_encodings:
#             matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE)
#             if True in matches:
#                 best_match_index = np.argmin(face_recognition.face_distance(known_face_encodings, face_encoding))
#                 if matches[best_match_index]:
#                     student_id = known_face_student_ids[best_match_index]
#                     student_info = student_details_map.get(student_id, {})
#                     name = student_info.get("name", "Unknown")
                    
#                     # 3. Mark attendance in the database
#                     db = next(get_db())
#                     if mark_attendance(db, student_id, camera_id):
#                         print(f"✅ Attendance marked for {name} from {camera_id}")
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "marked"})
#                     else:
#                         print(f"-> Attendance already marked today for {name}")
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "already_marked"})
#                     db.close()
    
#     if not recognized_students:
#         return {"status": "no_known_faces_recognized"}

#     return {"status": "success", "recognized_students": recognized_students}


# # This lets you run the API by executing "python api.py"
# if __name__ == "__main__":
#     uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)




























# # api.py (Fully Connected to Database)

# import uvicorn
# from fastapi import FastAPI, Form, UploadFile, File, HTTPException
# from datetime import date
# import os
# import cv2
# import numpy as np
# import face_recognition

# # Import all necessary components from your database file
# from database import (
#     get_db, School, Student, AttendanceLog,
#     sync_enrollment_data, load_known_faces_from_db, mark_attendance
# )

# # --- CONFIGURATION & API SETUP ---
# ENROLLMENT_DIR = "enrollment_images"
# RECOGNITION_TOLERANCE = 0.4
# app = FastAPI(title="MyLeading campus Attendance API")

# # --- GLOBAL VARIABLES & STARTUP EVENT ---
# known_face_encodings = []
# known_face_student_ids = []
# student_details_map = {}

# @app.on_event("startup")
# def load_data_on_startup():
#     """Loads all known faces from the DB into memory when the API starts."""
#     global known_face_encodings, known_face_student_ids, student_details_map
#     print("API starting up. Loading known faces...")
#     db = next(get_db())
#     # Run a sync at startup to ensure DB is up-to-date with enrollment folder
#     sync_enrollment_data(db, ENROLLMENT_DIR) 
#     known_face_encodings, known_face_student_ids, student_details_map = load_known_faces_from_db(db)
#     db.close()
#     print("Face data loaded. API is ready.")

# # --- FULLY CONNECTED API ENDPOINTS ---

# @app.get("/schools/")
# def get_all_schools():
#     """Returns a list of all schools from the database."""
#     db = next(get_db())
#     schools = db.query(School).all()
#     db.close()
#     return [{"id": school.id, "name": school.name} for school in schools]

# @app.get("/schools/{school_id}/students/")
# def get_students_for_school(school_id: int):
#     """Returns a list of all students for a specific school."""
#     db = next(get_db())
#     students = db.query(Student).filter(Student.school_id == school_id).all()
#     db.close()
#     if not students:
#         raise HTTPException(status_code=404, detail="No students found for this school.")
#     return [{"id": student.id, "name": student.name} for student in students]

# @app.post("/students/enroll")
# async def enroll_student(school_id: int = Form(...), student_name: str = Form(...), image: UploadFile = File(...)):
#     """Enrolls a new student by saving their photo and re-syncing the database."""
#     student_dir = os.path.join(ENROLLMENT_DIR, str(school_id), student_name)
#     os.makedirs(student_dir, exist_ok=True)
#     file_path = os.path.join(student_dir, image.filename)
#     with open(file_path, "wb") as buffer:
#         buffer.write(await image.read())
    
#     load_data_on_startup() # Reload all data after new enrollment
#     return {"status": "success", "message": f"Student '{student_name}' enrolled."}

# @app.post("/attendance/mark")
# async def mark_attendance_endpoint(camera_id: str = Form(...), image: UploadFile = File(...)):
#     """Receives an image from a camera and marks attendance."""
#     contents = await image.read()
#     nparr = np.frombuffer(contents, np.uint8)
#     frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb_frame)
#     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#     recognized_students = []
#     for face_encoding in face_encodings:
#         if known_face_encodings:
#             matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE)
#             if True in matches:
#                 best_match_index = np.argmin(face_recognition.face_distance(known_face_encodings, face_encoding))
#                 if matches[best_match_index]:
#                     student_id = known_face_student_ids[best_match_index]
#                     name = student_details_map.get(student_id, {}).get("name", "Unknown")
#                     db = next(get_db())
#                     if mark_attendance(db, student_id, camera_id):
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "marked"})
#                     else:
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "already_marked"})
#                     db.close()
#     return {"recognized_students": recognized_students}

# @app.get("/attendance/report/")
# def get_attendance_report(school_id: int, report_date: date):
#     """Gets the attendance report for a specific school and date from the database."""
#     db = next(get_db())
#     attendance_records = db.query(AttendanceLog).join(Student).filter(Student.school_id == school_id, AttendanceLog.attendance_date == report_date).all()
#     db.close()
    
#     report = [{"student_id": rec.student_id, "name": db.query(Student).get(rec.student_id).name, "first_seen": rec.first_seen_timestamp.strftime("%H:%M:%S")} for rec in attendance_records]
#     return {"school_id": school_id, "date": report_date, "attendees": report}

# if __name__ == "__main__":
#     uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

























#one true ciode for the api



# # api.py (Final S3 Version)

# import uvicorn
# from fastapi import FastAPI, Form, UploadFile, File, HTTPException
# from datetime import date, datetime, timedelta
# import os
# import cv2
# import numpy as np
# import face_recognition
# import boto3
# from botocore.exceptions import NoCredentialsError
# import shutil

# # Import all necessary components from your database file
# from database import (
#     get_db, School, Student, AttendanceLog,
#     sync_enrollment_data, load_known_faces_from_db, mark_attendance
# )

# # --- CONFIGURATION & API SETUP ---
# RECOGNITION_TOLERANCE = 0.4
# S3_BUCKET_NAME = "myleadingcampus-student-photos" # Change to your bucket name
# RE_ENCODE_INTERVAL_DAYS = 15
# TIMESTAMP_FILE = "last_sync_timestamp.txt"
# MAX_PHOTOS_PER_PERSON = 3
# TEMP_DIR = "/tmp/api_uploads" # Use a temporary directory for file operations

# os.makedirs(TEMP_DIR, exist_ok=True)
# app = FastAPI(title="MyLeading campus Attendance API")

# # --- GLOBAL VARIABLES & STARTUP EVENT ---
# known_face_encodings = []
# known_face_student_ids = []
# student_details_map = {}
# is_capture_day = False # Flag for self-learning photo capture

# @app.on_event("startup")
# def startup_event():
#     """On startup, check sync interval, sync if needed, and load faces."""
#     global is_capture_day
#     db = next(get_db())
    
#     if not os.path.exists(TIMESTAMP_FILE) or (datetime.now() - datetime.fromisoformat(open(TIMESTAMP_FILE).read()) > timedelta(days=RE_ENCODE_INTERVAL_DAYS)):
#         print("Activating 'Sync & Capture' mode for this session.")
#         is_capture_day = True
#         sync_enrollment_data(db)
#         with open(TIMESTAMP_FILE, "w") as f:
#             f.write(datetime.now().isoformat())
#     else:
#         print("Normal Day: Database sync not required.")
    
#     load_faces_into_memory(db)
#     db.close()

# def load_faces_into_memory(db_session):
#     """Helper to load/reload faces into global variables."""
#     global known_face_encodings, known_face_student_ids, student_details_map
#     known_face_encodings, known_face_student_ids, student_details_map = load_known_faces_from_db(db_session)

# # --- S3 HELPER ---
# def upload_to_s3(file_path, object_name):
#     s3_client = boto3.client('s3')
#     try:
#         s3_client.upload_file(file_path, S3_BUCKET_NAME, object_name)
#         return True
#     except Exception as e:
#         print(f"Error uploading to S3: {e}")
#         return False

# # --- FULLY CONNECTED API ENDPOINTS ---

# @app.post("/students/enroll")
# async def enroll_student(school_id: int = Form(...), student_name: str = Form(...), image: UploadFile = File(...)):
#     """Enrolls a student by uploading their photo to S3 and re-syncing the database."""
#     s3_object_name = f"{school_id}/{student_name}/{image.filename}"
#     temp_file_path = os.path.join(TEMP_DIR, image.filename)

#     with open(temp_file_path, "wb") as buffer:
#         shutil.copyfileobj(image.file, buffer)
    
#     if upload_to_s3(temp_file_path, s3_object_name):
#         db = next(get_db())
#         sync_enrollment_data(db) # Re-sync to enroll the new student from S3
#         load_faces_into_memory(db) # Reload faces into memory
#         db.close()
#         os.remove(temp_file_path)
#         return {"status": "success", "message": f"Student '{student_name}' enrolled."}
#     else:
#         os.remove(temp_file_path)
#         raise HTTPException(status_code=500, detail="Could not upload photo to S3.")

# @app.post("/attendance/mark")
# async def mark_attendance_endpoint(camera_id: str = Form(...), image: UploadFile = File(...)):
#     """Receives an image, recognizes faces, and marks attendance. Captures photos on sync days."""
#     contents = await image.read()
#     nparr = np.frombuffer(contents, np.uint8)
#     frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb_frame)
#     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#     recognized_students = []
#     for face_encoding in face_encodings:
#         if known_face_encodings:
#             matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE)
#             if True in matches:
#                 best_match_index = np.argmin(face_recognition.face_distance(known_face_encodings, face_encoding))
#                 if matches[best_match_index]:
#                     student_id = known_face_student_ids[best_match_index]
#                     db = next(get_db())
#                     if mark_attendance(db, student_id, camera_id):
#                         student_info = student_details_map.get(student_id)
#                         name = student_info.get("name", "Unknown")
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "marked"})

#                         # Self-learning photo capture logic
#                         if is_capture_day and student_info:
#                             filename = f"{name}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
#                             s3_object_name = f"{student_info['school_id']}/{name}/{filename}"
#                             temp_file_path = os.path.join(TEMP_DIR, filename)
#                             cv2.imwrite(temp_file_path, frame)
#                             if upload_to_s3(temp_file_path, s3_object_name):
#                                 print(f"📸 [Capture Mode ON] Saved new image for {name} to S3.")
#                             os.remove(temp_file_path)
#                     db.close()

#     return {"recognized_students": recognized_students}

# # ... (GET endpoints for reports and schools are unchanged) ...
# @app.get("/schools/")
# def get_all_schools():
#     db = next(get_db())
#     schools = db.query(School).all()
#     db.close()
#     return [{"id": school.id, "name": school.name} for school in schools]

# @app.get("/schools/{school_id}/students/")
# def get_students_for_school(school_id: int):
#     db = next(get_db())
#     students = db.query(Student).filter(Student.school_id == school_id).all()
#     db.close()
#     if not students:
#         raise HTTPException(status_code=404, detail="No students found for this school.")
#     return [{"id": student.id, "name": student.name} for student in students]

# @app.get("/attendance/report/")
# def get_attendance_report(school_id: int, report_date: date):
#     db = next(get_db())
#     report_data = []
#     attendance_records = db.query(AttendanceLog).join(Student).filter(Student.school_id == school_id, AttendanceLog.attendance_date == report_date).all()
#     for rec in attendance_records:
#         student_name = student_details_map.get(rec.student_id, {}).get("name", "N/A")
#         report_data.append({"student_id": rec.student_id, "name": student_name, "first_seen": rec.first_seen_timestamp.strftime("%H:%M:%S")})
#     db.close()
#     return {"school_id": school_id, "date": report_date, "attendees": report_data}


# if __name__ == "__main__":
#     uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
















































#21st aug changes 



# # api.py (Fully Connected to Database)

# import uvicorn
# from fastapi import FastAPI, Form, UploadFile, File, HTTPException
# from datetime import date
# import os
# import cv2
# import numpy as np
# import face_recognition

# # Import all necessary components from your database file
# from database import (
#     get_db, School, Student, AttendanceLog,
#     sync_enrollment_data, load_known_faces_from_db, mark_attendance
# )

# # --- CONFIGURATION & API SETUP ---
# ENROLLMENT_DIR = "enrollment_images"
# RECOGNITION_TOLERANCE = 0.4
# app = FastAPI(title="MyLeading campus Attendance API")

# # --- GLOBAL VARIABLES & STARTUP EVENT ---
# known_face_encodings = []
# known_face_student_ids = []
# student_details_map = {}

# @app.on_event("startup")
# def load_data_on_startup():
#     """Loads all known faces from the DB into memory when the API starts."""
#     global known_face_encodings, known_face_student_ids, student_details_map
#     print("API starting up. Loading known faces...")
#     db = next(get_db())
#     # Run a sync at startup to ensure DB is up-to-date with enrollment folder
#     sync_enrollment_data(db, ENROLLMENT_DIR) 
#     known_face_encodings, known_face_student_ids, student_details_map = load_known_faces_from_db(db)
#     db.close()
#     print("Face data loaded. API is ready.")

# # --- FULLY CONNECTED API ENDPOINTS ---

# @app.get("/schools/")
# def get_all_schools():
#     """Returns a list of all schools from the database."""
#     db = next(get_db())
#     schools = db.query(School).all()
#     db.close()
#     return [{"id": school.id, "name": school.name} for school in schools]

# @app.get("/schools/{school_id}/students/")
# def get_students_for_school(school_id: int):
#     """Returns a list of all students for a specific school."""
#     db = next(get_db())
#     students = db.query(Student).filter(Student.school_id == school_id).all()
#     db.close()
#     if not students:
#         raise HTTPException(status_code=404, detail="No students found for this school.")
#     return [{"id": student.id, "name": student.name} for student in students]

# @app.post("/students/enroll")
# async def enroll_student(school_id: int = Form(...), student_name: str = Form(...), image: UploadFile = File(...)):
#     """Enrolls a new student by saving their photo and re-syncing the database."""
#     student_dir = os.path.join(ENROLLMENT_DIR, str(school_id), student_name)
#     os.makedirs(student_dir, exist_ok=True)
#     file_path = os.path.join(student_dir, image.filename)
#     with open(file_path, "wb") as buffer:
#         buffer.write(await image.read())
    
#     load_data_on_startup() # Reload all data after new enrollment
#     return {"status": "success", "message": f"Student '{student_name}' enrolled."}

# @app.post("/attendance/mark")
# async def mark_attendance_endpoint(camera_id: str = Form(...), image: UploadFile = File(...)):
#     """Receives an image from a camera and marks attendance."""
#     contents = await image.read()
#     nparr = np.frombuffer(contents, np.uint8)
#     frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb_frame)
#     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#     recognized_students = []
#     for face_encoding in face_encodings:
#         if known_face_encodings:
#             matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE)
#             if True in matches:
#                 best_match_index = np.argmin(face_recognition.face_distance(known_face_encodings, face_encoding))
#                 if matches[best_match_index]:
#                     student_id = known_face_student_ids[best_match_index]
#                     name = student_details_map.get(student_id, {}).get("name", "Unknown")
#                     db = next(get_db())
#                     if mark_attendance(db, student_id, camera_id):
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "marked"})
#                     else:
#                         recognized_students.append({"student_id": student_id, "name": name, "status": "already_marked"})
#                     db.close()
#     return {"recognized_students": recognized_students}

# @app.get("/attendance/report/")
# def get_attendance_report(school_id: int, report_date: date):
#     """Gets the attendance report for a specific school and date from the database."""
#     db = next(get_db())
#     attendance_records = db.query(AttendanceLog).join(Student).filter(Student.school_id == school_id, AttendanceLog.attendance_date == report_date).all()
#     db.close()
    
#     report = [{"student_id": rec.student_id, "name": db.query(Student).get(rec.student_id).name, "first_seen": rec.first_seen_timestamp.strftime("%H:%M:%S")} for rec in attendance_records]
#     return {"school_id": school_id, "date": report_date, "attendees": report}

# if __name__ == "__main__":
#     uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)















#changes 1


# api.py (Optimized: encodings stored as .pkl files; DB stores only file paths)

import uvicorn
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from datetime import date, datetime
import os
import cv2
import numpy as np
import face_recognition
import pickle
import time

# Import DB utilities/models
from database import (
    get_db, School, Student, AttendanceLog,
    sync_enrollment_data, load_known_faces_from_db, mark_attendance,
    ENCODINGS_DIR  # use the same directory constant as database.py
)

# --- CONFIGURATION & API SETUP ---
RECOGNITION_TOLERANCE = 0.4
app = FastAPI(title="MyLeading campus Attendance API")

# --- GLOBALS ---
known_face_encodings = []
known_face_student_ids = []
student_details_map = {}


def _ensure_school_and_student(db, school_id: int, student_name: str) -> Student:
    """Mirror logic used by database.sync_enrollment_data to get/create Student."""
    # Ensure school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        school = School(id=school_id, name=f"School {school_id}")
        db.add(school)
        db.commit()
        db.refresh(school)

    # Ensure student exists
    student = db.query(Student).filter(
        Student.name == student_name, Student.school_id == school_id
    ).first()
    if not student:
        # Increment serial
        school_to_update = db.query(School).filter(School.id == school_id).with_for_update().one()
        new_serial = school_to_update.last_student_serial + 1
        new_student_id = f"{school_to_update.id}{new_serial:04d}"
        school_to_update.last_student_serial = new_serial
        student = Student(id=new_student_id, school_id=school_to_update.id, name=student_name)
        db.add(student)
        db.commit()
    return student


@app.on_event("startup")
def load_data_on_startup():
    """Load encodings from .pkl file paths stored in DB into memory."""
    global known_face_encodings, known_face_student_ids, student_details_map
    print("API starting up. Loading known faces...")

    db = next(get_db())

    # DEV/compat: scan ENCODINGS_DIR to auto-register .pkl files into DB if any
    sync_enrollment_data(db, ENCODINGS_DIR)

    # Load into memory from paths in DB
    known_face_encodings, known_face_student_ids, student_details_map = load_known_faces_from_db(db)

    db.close()
    print("Face data loaded. API is ready.")


# --- API ENDPOINTS ---

@app.get("/schools/")
def get_all_schools():
    db = next(get_db())
    schools = db.query(School).all()
    out = [{"id": s.id, "name": s.name} for s in schools]
    db.close()
    return out


@app.get("/schools/{school_id}/students/")
def get_students_for_school(school_id: int):
    db = next(get_db())
    students = db.query(Student).filter(Student.school_id == school_id).all()
    db.close()
    if not students:
        raise HTTPException(status_code=404, detail="No students found for this school.")
    return [{"id": st.id, "name": st.name} for st in students]


@app.post("/students/enroll")
async def enroll_student(
    school_id: int = Form(...),
    student_name: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Enroll a new student:
      - Ensure School + Student exist (generate student_id if new)
      - Compute encoding from uploaded image
      - Save encoding to .pkl at ENCODINGS_DIR/<school_id>/<student_name>/<unique>.pkl
      - Insert FaceEncoding row with path (no binary encoding in DB)
      - Reload in-memory encodings
    """
    # Read uploaded image bytes
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image data.")

    # Extract encoding
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encs = face_recognition.face_encodings(rgb_frame, face_locations)
    if not face_encs:
        raise HTTPException(status_code=400, detail="No face found in the uploaded image.")

    encoding = np.asarray(face_encs[0], dtype=np.float64)

    db = next(get_db())
    # Ensure entities
    student = _ensure_school_and_student(db, school_id, student_name)

    # Save encoding to .pkl
    save_dir = os.path.join(ENCODINGS_DIR, str(school_id), student_name)
    os.makedirs(save_dir, exist_ok=True)
    unique_name = f"enc_{int(time.time()*1000)}.pkl"
    save_path = os.path.join(save_dir, unique_name)

    try:
        with open(save_path, "wb") as f:
            pickle.dump(encoding, f)
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Failed to persist encoding file: {e}")

    # Register in DB (store only path; keep encoding binary empty for legacy schema)
    from database import FaceEncoding  # local import to avoid circular
    fe = FaceEncoding(student_id=student.id, encoding=b"", image_path=save_path)
    db.add(fe)
    db.commit()
    db.close()

    # Reload all encodings into memory
    load_data_on_startup()

    return {"status": "success", "message": f"Student '{student_name}' enrolled.", "student_id": student.id}


@app.post("/attendance/mark")
async def mark_attendance_endpoint(
    camera_id: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Receives an image from a camera and marks attendance.
    Uses in-memory encodings that were loaded from .pkl files at startup/refresh.
    """
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return {"recognized_students": []}

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    recognized_students = []
    for face_encoding in face_encodings:
        if known_face_encodings:
            matches = face_recognition.compare_faces(
                known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE
            )
            if True in matches:
                best_match_index = np.argmin(
                    face_recognition.face_distance(known_face_encodings, face_encoding)
                )
                if matches[best_match_index]:
                    student_id = known_face_student_ids[best_match_index]
                    name = student_details_map.get(student_id, {}).get("name", "Unknown")
                    db = next(get_db())
                    if mark_attendance(db, student_id, camera_id):
                        recognized_students.append({"student_id": student_id, "name": name, "status": "marked"})
                    else:
                        recognized_students.append({"student_id": student_id, "name": name, "status": "already_marked"})
                    db.close()

    return {"recognized_students": recognized_students}


@app.get("/attendance/report/")
def get_attendance_report(school_id: int, report_date: date):
    """
    Get attendance for a school on a given date.
    """
    db = next(get_db())
    # Join to fetch names in one go (avoid using session after close)
    q = (
        db.query(AttendanceLog, Student.name)
        .join(Student, AttendanceLog.student_id == Student.id)
        .filter(Student.school_id == school_id, AttendanceLog.attendance_date == report_date)
        .all()
    )
    attendees = [
        {
            "student_id": rec.AttendanceLog.student_id,
            "name": rec.name,
            "first_seen": rec.AttendanceLog.first_seen_timestamp.strftime("%H:%M:%S"),
        }
        for rec in q
    ]
    db.close()
    return {"school_id": school_id, "date": report_date, "attendees": attendees}


if __name__ == "__main__":
    # Use reload only in dev
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)






