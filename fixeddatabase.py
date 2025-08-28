# #New code, updated 14th aug 2025
# # database.py (Final S3 Version)

# import sqlalchemy
# from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, Date, ForeignKey, UniqueConstraint
# from sqlalchemy.orm import sessionmaker, declarative_base
# from sqlalchemy.exc import IntegrityError
# from datetime import datetime
# import numpy as np
# import os
# import face_recognition
# import boto3 # Added for S3 access

# # --- CONFIGURATION ---
# DB_USER = "postgres"
# DB_PASSWORD = "your_password" # Change to your PostgreSQL password
# DB_HOST = "localhost" # This will change to your RDS endpoint later
# DB_NAME = "attendance_system"
# S3_BUCKET_NAME = "myleadingcampus-student-photos" # IMPORTANT: Change to your S3 bucket name

# DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()

# # --- TABLE DEFINITIONS (Unchanged) ---
# class School(Base):
#     __tablename__ = "schools"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, unique=True, nullable=False)
#     last_student_serial = Column(Integer, default=0, nullable=False)

# class Student(Base):
#     __tablename__ = "students"
#     id = Column(String, primary_key=True, index=True)
#     school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
#     name = Column(String, nullable=False)

# class FaceEncoding(Base):
#     __tablename__ = "face_encodings"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     encoding = Column(LargeBinary, nullable=False)
#     image_path = Column(String, unique=True, nullable=False) # This will be the S3 object key

# class AttendanceLog(Base):
#     __tablename__ = "attendance_logs"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     attendance_date = Column(Date, nullable=False)
#     first_seen_timestamp = Column(DateTime, nullable=False)
#     camera_id = Column(String)
#     __table_args__ = (UniqueConstraint('student_id', 'attendance_date', name='_student_date_uc'),)

# # --- DATABASE HELPER FUNCTIONS ---
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# def create_database_and_tables():
#     # This function is unchanged and correct
#     try:
#         temp_engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres", isolation_level="AUTOCOMMIT")
#         with temp_engine.connect() as connection:
#             result = connection.execute(sqlalchemy.text(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"))
#             if not result.first():
#                 connection.execute(sqlalchemy.text(f'CREATE DATABASE "{DB_NAME}"'))
#         Base.metadata.create_all(bind=engine)
#         print("Database and tables are ready.")
#     except Exception as e:
#         print(f"Error during database setup: {e}")
#         exit()

# def sync_enrollment_data(db):
#     """MODIFIED: This function now syncs the DB by reading images directly from S3."""
#     print("\n=== Synchronizing Faces with Database from S3 ===")
#     s3_client = boto3.client('s3')
#     synced_photos = 0
#     temp_dir = "/tmp/downloads"
#     os.makedirs(temp_dir, exist_ok=True)

#     try:
#         paginator = s3_client.get_paginator('list_objects_v2')
#         pages = paginator.paginate(Bucket=S3_BUCKET_NAME)
#         for page in pages:
#             if 'Contents' not in page: continue
#             for item in page['Contents']:
#                 s3_path = item['Key']
#                 # Path is expected to be: school_id/student_name/filename.jpg
#                 try:
#                     school_id_str, student_name, filename = s3_path.split('/')
#                     if not filename: continue # Skip folder prefixes
#                     school_id = int(school_id_str)
#                 except (ValueError, IndexError):
#                     continue

#                 if db.query(FaceEncoding).filter(FaceEncoding.image_path == s3_path).first(): continue

#                 print(f"  Found new image in S3 for {student_name}. Processing: {s3_path}")
                
#                 temp_file_path = os.path.join(temp_dir, os.path.basename(s3_path))
#                 s3_client.download_file(S3_BUCKET_NAME, s3_path, temp_file_path)

#                 student = db.query(Student).filter(Student.name == student_name, Student.school_id == school_id).first()
#                 if not student:
#                     school = db.query(School).filter(School.id == school_id).first()
#                     if not school:
#                         school = School(id=school_id, name=f"School {school_id}")
#                         db.add(school)
#                         db.commit()
                    
#                     school_to_update = db.query(School).filter(School.id == school_id).with_for_update().one()
#                     new_serial = school_to_update.last_student_serial + 1
#                     new_student_id = f"{school_to_update.id}{new_serial:04d}"
#                     school_to_update.last_student_serial = new_serial
#                     student = Student(id=new_student_id, school_id=school_to_update.id, name=student_name)
#                     db.add(student)
#                     db.commit()

#                 try:
#                     image = face_recognition.load_image_file(temp_file_path)
#                     encodings = face_recognition.face_encodings(image)
#                     if encodings:
#                         db.add(FaceEncoding(student_id=student.id, encoding=encodings[0].tobytes(), image_path=s3_path))
#                         synced_photos += 1
#                 except Exception as e:
#                     print(f"    Could not process {filename}: {e}")
                
#                 os.remove(temp_file_path)
#         db.commit()
#     except Exception as e:
#         print(f"An error occurred during S3 sync: {e}")
    
#     if synced_photos > 0:
#         print(f"S3 sync complete. Added {synced_photos} new photo encodings.")
#     else:
#         print("S3 sync complete. No new photos found to encode.")

# def load_known_faces_from_db(db):
#     # This function is unchanged and correct
#     print("Loading known faces from database...")
#     encodings_with_details = db.query(FaceEncoding, Student.name, Student.school_id).join(Student, FaceEncoding.student_id == Student.id).all()
#     if not encodings_with_details: return [], [], {}
#     known_face_encodings = [np.frombuffer(res.FaceEncoding.encoding, dtype=np.float64) for res in encodings_with_details]
#     known_face_student_ids = [res.FaceEncoding.student_id for res in encodings_with_details]
#     student_details_map = {res.FaceEncoding.student_id: {"name": res.name, "school_id": res.school_id} for res in encodings_with_details}
#     print(f"Loaded {len(known_face_encodings)} faces.")
#     return known_face_encodings, known_face_student_ids, student_details_map

# def mark_attendance(db, student_id, camera_id):
#     # This function is unchanged and correct
#     try:
#         db.add(AttendanceLog(student_id=student_id, attendance_date=datetime.now().date(), first_seen_timestamp=datetime.now(), camera_id=str(camera_id)))
#         db.commit()
#         return True
#     except IntegrityError:
#         db.rollback()
#         return False

































# # database.py (Final Corrected Indentation)

# import sqlalchemy
# from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, Date, ForeignKey, UniqueConstraint
# from sqlalchemy.orm import sessionmaker, declarative_base
# from sqlalchemy.exc import IntegrityError
# from datetime import datetime
# import numpy as np
# import os
# import face_recognition

# # --- DATABASE CONFIGURATION ---
# DB_USER = "postgres"
# DB_PASSWORD = "aman" # Your PostgreSQL password
# DB_HOST = "localhost"
# DB_PORT = "5432"
# DB_NAME = "attendance_system"

# DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()

# # --- FINAL TABLE DEFINITIONS (With Correct Indentation) ---
# class School(Base):
#     __tablename__ = "schools"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, unique=True, nullable=False)
#     last_student_serial = Column(Integer, default=0, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class Student(Base):
#     __tablename__ = "students"
#     id = Column(String, primary_key=True, index=True)
#     school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
#     name = Column(String, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class FaceEncoding(Base):
#     __tablename__ = "face_encodings"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     encoding = Column(LargeBinary, nullable=False)
#     image_path = Column(String, unique=True, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class AttendanceLog(Base):
#     __tablename__ = "attendance_logs"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     attendance_date = Column(Date, nullable=False)
#     first_seen_timestamp = Column(DateTime, nullable=False)
#     camera_id = Column(String)
#     __table_args__ = (UniqueConstraint('student_id', 'attendance_date', name='_student_date_uc'),)

# # --- DATABASE HELPER FUNCTIONS ---
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# def create_database_and_tables():
#     try:
#         temp_engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres", isolation_level="AUTOCOMMIT")
#         with temp_engine.connect() as connection:
#             result = connection.execute(sqlalchemy.text(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"))
#             if not result.first():
#                 connection.execute(sqlalchemy.text(f'CREATE DATABASE "{DB_NAME}"'))
#                 print(f"Database '{DB_NAME}' created.")
        
#         Base.metadata.create_all(bind=engine)
#         print("Database and tables are ready.")
    
#     except Exception as e:
#         print(f"Error during database setup: {e}")
#         exit()

# def sync_enrollment_data(db, enrollment_dir):
#     print("\n=== Synchronizing Faces with Database ===")
#     os.makedirs(enrollment_dir, exist_ok=True)
#     synced_photos = 0

#     for school_id_str in os.listdir(enrollment_dir):
#         school_folder_path = os.path.join(enrollment_dir, school_id_str)
#         if not os.path.isdir(school_folder_path): continue
        
#         school_id = int(school_id_str)
#         if not db.query(School).filter(School.id == school_id).first():
#             db.add(School(id=school_id, name=f"School {school_id}"))
#             db.commit()

#         for student_name in os.listdir(school_folder_path):
#             student_folder_path = os.path.join(school_folder_path, student_name)
#             if not os.path.isdir(student_folder_path): continue

#             student = db.query(Student).filter(Student.name == student_name, Student.school_id == school_id).first()
#             if not student:
#                 school_to_update = db.query(School).filter(School.id == school_id).with_for_update().one()
#                 new_serial = school_to_update.last_student_serial + 1
#                 new_student_id = f"{school_to_update.id}{new_serial:04d}"
#                 school_to_update.last_student_serial = new_serial
#                 student = Student(id=new_student_id, school_id=school_to_update.id, name=student_name)
#                 db.add(student)
#                 db.commit()
#                 print(f"Enrolling new student '{student_name}' with ID: {student.id}")

#             for filename in os.listdir(student_folder_path):
#                 file_path = os.path.join(student_folder_path, filename)
#                 if not filename.lower().endswith(('.jpg', '.jpeg', '.png')): continue
#                 if db.query(FaceEncoding).filter(FaceEncoding.image_path == file_path).first(): continue

#                 print(f"  Found new image for {student_name}. Encoding: {filename}")
#                 try:
#                     image = face_recognition.load_image_file(file_path)
#                     encodings = face_recognition.face_encodings(image)
#                     if encodings:
#                         db.add(FaceEncoding(student_id=student.id, encoding=encodings[0].tobytes(), image_path=file_path))
#                         synced_photos += 1
#                 except Exception as e:
#                     print(f"    Could not process {filename}: {e}")
#     db.commit()
#     if synced_photos > 0:
#         print(f"Sync complete. Added {synced_photos} new photo encodings.")
#     else:
#         print("Sync complete. No new photos found.")

# def load_known_faces_from_db(db):
#     print("Loading known faces from database...")
#     encodings_with_details = db.query(FaceEncoding, Student.name, Student.school_id).join(Student, FaceEncoding.student_id == Student.id).all()
#     if not encodings_with_details: return [], [], {}
#     known_face_encodings = [np.frombuffer(res.FaceEncoding.encoding, dtype=np.float64) for res in encodings_with_details]
#     known_face_student_ids = [res.FaceEncoding.student_id for res in encodings_with_details]
#     student_details_map = {res.FaceEncoding.student_id: {"name": res.name, "school_id": res.school_id} for res in encodings_with_details}
#     print(f"Loaded {len(known_face_encodings)} faces.")
#     return known_face_encodings, known_face_student_ids, student_details_map

# def mark_attendance(db, student_id, camera_id):
#     try:
#         db.add(AttendanceLog(student_id=student_id, attendance_date=datetime.now().date(), first_seen_timestamp=datetime.now(), camera_id=str(camera_id)))
#         db.commit()
#         return True
#     except IntegrityError:
#         db.rollback()
#         return False























# # # database.py

# # import sqlalchemy
# # from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, Date, ForeignKey, UniqueConstraint
# # from sqlalchemy.orm import sessionmaker, declarative_base, joinedload
# # from sqlalchemy.exc import IntegrityError
# # from datetime import datetime
# # import numpy as np
# # import os
# # import face_recognition

# # # --- DATABASE CONFIGURATION ---
# # DB_USER = "postgres"
# # DB_PASSWORD = "aman" # IMPORTANT: Change this to your PostgreSQL password
# # DB_HOST = "localhost"
# # DB_PORT = "5432"
# # DB_NAME = "attendance_system"

# # DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# # engine = create_engine(DATABASE_URL)
# # SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# # Base = declarative_base()

# # # --- FINAL TABLE DEFINITIONS ---
# # class School(Base):
# #     __tablename__ = "schools"
# #     id = Column(Integer, primary_key=True, index=True)
# #     name = Column(String, unique=True, nullable=False)
# #     last_student_serial = Column(Integer, default=0, nullable=False)

# # class Student(Base):
# #     __tablename__ = "students"
# #     id = Column(String, primary_key=True, index=True)
# #     school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
# #     name = Column(String, nullable=False)

# # class FaceEncoding(Base):
# #     __tablename__ = "face_encodings"
# #     id = Column(Integer, primary_key=True, index=True)
# #     student_id = Column(String, ForeignKey('students.id'), nullable=False)
# #     encoding = Column(LargeBinary, nullable=False)
# #     image_path = Column(String, unique=True, nullable=False)

# # class AttendanceLog(Base):
# #     __tablename__ = "attendance_logs"
# #     id = Column(Integer, primary_key=True, index=True)
# #     student_id = Column(String, ForeignKey('students.id'), nullable=False)
# #     attendance_date = Column(Date, nullable=False)
# #     first_seen_timestamp = Column(DateTime, nullable=False)
# #     camera_id = Column(String)
# #     __table_args__ = (UniqueConstraint('student_id', 'attendance_date', name='_student_date_uc'),)

# # # --- DATABASE HELPER FUNCTIONS ---
# # def get_db():
# #     db = SessionLocal()
# #     try:
# #         yield db
# #     finally:
# #         db.close()

# # def create_database_and_tables():
# #     try:
# #         temp_engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres", isolation_level="AUTOCOMMIT")
# #         with temp_engine.connect() as connection:
# #             result = connection.execute(sqlalchemy.text(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"))
# #             if not result.first():
# #                 connection.execute(sqlalchemy.text(f'CREATE DATABASE "{DB_NAME}"'))
# #                 print(f"Database '{DB_NAME}' created.")
# #         Base.metadata.create_all(bind=engine)
# #         print("Database and tables are ready.")
# #     except Exception as e:
# #         print(f"Error during database setup: {e}")
# #         exit()

# # def sync_enrollment_data(db, enrollment_dir):
# #     """This is the 're-encoding' function. It syncs new schools, students, and photos with the DB."""
# #     print("\n=== Synchronizing Faces with Database ===")
# #     os.makedirs(enrollment_dir, exist_ok=True)
# #     synced_photos = 0

# #     for school_id_str in os.listdir(enrollment_dir):
# #         school_folder_path = os.path.join(enrollment_dir, school_id_str)
# #         if not os.path.isdir(school_folder_path): continue
        
# #         school_id = int(school_id_str)
# #         if not db.query(School).filter(School.id == school_id).first():
# #             db.add(School(id=school_id, name=f"School {school_id}"))
# #             db.commit()

# #         for student_name in os.listdir(school_folder_path):
# #             student_folder_path = os.path.join(school_folder_path, student_name)
# #             if not os.path.isdir(student_folder_path): continue

# #             student = db.query(Student).filter(Student.name == student_name, Student.school_id == school_id).first()
# #             if not student:
# #                 school_to_update = db.query(School).filter(School.id == school_id).with_for_update().one()
# #                 new_serial = school_to_update.last_student_serial + 1
# #                 new_student_id = f"{school_to_update.id}{new_serial:04d}"
# #                 school_to_update.last_student_serial = new_serial
# #                 student = Student(id=new_student_id, school_id=school_to_update.id, name=student_name)
# #                 db.add(student)
# #                 db.commit()
# #                 print(f"Enrolling new student '{student_name}' with ID: {student.id}")

# #             for filename in os.listdir(student_folder_path):
# #                 file_path = os.path.join(student_folder_path, filename)
# #                 if not filename.lower().endswith(('.jpg', '.jpeg', '.png')): continue
# #                 if db.query(FaceEncoding).filter(FaceEncoding.image_path == file_path).first(): continue

# #                 print(f"  Found new image for {student_name}. Encoding: {filename}")
# #                 try:
# #                     image = face_recognition.load_image_file(file_path)
# #                     encodings = face_recognition.face_encodings(image)
# #                     if encodings:
# #                         db.add(FaceEncoding(student_id=student.id, encoding=encodings[0].tobytes(), image_path=file_path))
# #                         synced_photos += 1
# #                 except Exception as e:
# #                     print(f"    Could not process {filename}: {e}")
# #     db.commit()
# #     if synced_photos > 0:
# #         print(f"Sync complete. Added {synced_photos} new photo encodings.")
# #     else:
# #         print("Sync complete. No new photos found.")

# # def load_known_faces_from_db(db):
# #     print("Loading known faces from database...")
# #     encodings_with_details = db.query(FaceEncoding, Student.name, Student.school_id).join(Student, FaceEncoding.student_id == Student.id).all()
# #     if not encodings_with_details: return [], [], {}
# #     known_face_encodings = [np.frombuffer(res.FaceEncoding.encoding, dtype=np.float64) for res in encodings_with_details]
# #     known_face_student_ids = [res.FaceEncoding.student_id for res in encodings_with_details]
# #     student_details_map = {res.FaceEncoding.student_id: {"name": res.name, "school_id": res.school_id} for res in encodings_with_details}
# #     print(f"Loaded {len(known_face_encodings)} faces.")
# #     return known_face_encodings, known_face_student_ids, student_details_map

# # def mark_attendance(db, student_id, camera_id):
# #     try:
# #         db.add(AttendanceLog(student_id=student_id, attendance_date=datetime.now().date(), first_seen_timestamp=datetime.now(), camera_id=str(camera_id)))
# #         db.commit()
# #         return True
# #     except IntegrityError:
# #         db.rollback()
# #         return False


















































#21st aug changes 








# # database.py (Final Corrected Version)

# import sqlalchemy
# from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, Date, ForeignKey, UniqueConstraint
# from sqlalchemy.orm import sessionmaker, declarative_base
# from sqlalchemy.exc import IntegrityError
# from datetime import datetime
# import numpy as np
# import os
# import face_recognition

# # --- DATABASE CONFIGURATION ---
# DB_USER = "postgres"
# DB_PASSWORD = "aman" # Your PostgreSQL password
# DB_HOST = "localhost"
# DB_PORT = "5432"
# DB_NAME = "attendance_system"



# # # --- DATABASE CONFIGURATION ---
# # DB_USER = "mlc_devdb_master"
# # DB_PASSWORD = "mc0RYjhPAfGhfaCHFDWX"
# # DB_HOST = "mlc-dev-db-pgsql-01.cdego6cy2f2o.ap-south-1.rds.amazonaws.com"
# # DB_PORT = "5432"
# # DB_NAME = "mlc_dev_db_01"

# DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()

# # --- FINAL TABLE DEFINITIONS (With _tablename_ and _table_args_ corrected) ---
# class School(Base):
#     __tablename__ = "schools"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, unique=True, nullable=False)
#     last_student_serial = Column(Integer, default=0, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class Student(Base):
#     __tablename__ = "students"
#     id = Column(String, primary_key=True, index=True)
#     school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
#     name = Column(String, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class FaceEncoding(Base):
#     __tablename__ = "face_encodings"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     encoding = Column(LargeBinary, nullable=False)
#     image_path = Column(String, unique=True, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class AttendanceLog(Base):
#     __tablename__ = "attendance_logs"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     attendance_date = Column(Date, nullable=False)
#     first_seen_timestamp = Column(DateTime, nullable=False)
#     camera_id = Column(String)
#     _table_args_ = (UniqueConstraint('student_id', 'attendance_date', name='_student_date_uc'),)

# # --- DATABASE HELPER FUNCTIONS ---
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# def create_database_and_tables():
#     try:
#         temp_engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres", isolation_level="AUTOCOMMIT")
#         with temp_engine.connect() as connection:
#             result = connection.execute(sqlalchemy.text(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"))
#             if not result.first():
#                 connection.execute(sqlalchemy.text(f'CREATE DATABASE "{DB_NAME}"'))
#                 print(f"Database '{DB_NAME}' created.")
        
#         Base.metadata.create_all(bind=engine)
#         print("Database and tables are ready.")
    
#     except Exception as e:
#         print(f"Error during database setup: {e}")
#         exit()
# create_database_and_tables()

# def sync_enrollment_data(db, enrollment_dir):
#     print("\n=== Synchronizing Faces with Database ===")
#     os.makedirs(enrollment_dir, exist_ok=True)
#     synced_photos = 0

#     for school_id_str in os.listdir(enrollment_dir):
#         school_folder_path = os.path.join(enrollment_dir, school_id_str)
#         if not os.path.isdir(school_folder_path): continue
        
#         school_id = int(school_id_str)
#         if not db.query(School).filter(School.id == school_id).first():
#             db.add(School(id=school_id, name=f"School {school_id}"))
#             db.commit()

#         for student_name in os.listdir(school_folder_path):
#             student_folder_path = os.path.join(school_folder_path, student_name)
#             if not os.path.isdir(student_folder_path): continue

#             student = db.query(Student).filter(Student.name == student_name, Student.school_id == school_id).first()
#             if not student:
#                 school_to_update = db.query(School).filter(School.id == school_id).with_for_update().one()
#                 new_serial = school_to_update.last_student_serial + 1
#                 new_student_id = f"{school_to_update.id}{new_serial:04d}"
#                 school_to_update.last_student_serial = new_serial
#                 student = Student(id=new_student_id, school_id=school_to_update.id, name=student_name)
#                 db.add(student)
#                 db.commit()
#                 print(f"Enrolling new student '{student_name}' with ID: {student.id}")

#             for filename in os.listdir(student_folder_path):
#                 file_path = os.path.join(student_folder_path, filename)
#                 if not filename.lower().endswith(('.jpg', '.jpeg', '.png')): continue
#                 if db.query(FaceEncoding).filter(FaceEncoding.image_path == file_path).first(): continue

#                 print(f"  Found new image for {student_name}. Encoding: {filename}")
#                 try:
#                     image = face_recognition.load_image_file(file_path)
#                     encodings = face_recognition.face_encodings(image)
#                     if encodings:
#                         db.add(FaceEncoding(student_id=student.id, encoding=encodings[0].tobytes(), image_path=file_path))
#                         synced_photos += 1
#                 except Exception as e:
#                     print(f"    Could not process {filename}: {e}")
#     db.commit()
#     if synced_photos > 0:
#         print(f"Sync complete. Added {synced_photos} new photo encodings.")
#     else:
#         print("Sync complete. No new photos found.")

# def load_known_faces_from_db(db):
#     print("Loading known faces from database...")
#     encodings_with_details = db.query(FaceEncoding, Student.name, Student.school_id).join(Student, FaceEncoding.student_id == Student.id).all()
#     if not encodings_with_details: return [], [], {}
#     known_face_encodings = [np.frombuffer(res.FaceEncoding.encoding, dtype=np.float64) for res in encodings_with_details]
#     known_face_student_ids = [res.FaceEncoding.student_id for res in encodings_with_details]
#     student_details_map = {res.FaceEncoding.student_id: {"name": res.name, "school_id": res.school_id} for res in encodings_with_details}
#     print(f"Loaded {len(known_face_encodings)} faces.")
#     return known_face_encodings, known_face_student_ids, student_details_map

# def mark_attendance(db, student_id, camera_id):
#     try:
#         db.add(AttendanceLog(student_id=student_id, attendance_date=datetime.now().date(), first_seen_timestamp=datetime.now(), camera_id=str(camera_id)))
#         db.commit()
#         return True
#     except IntegrityError:
#         db.rollback()
#         return False




#changes 1


# database.py (Optimized: store encoding files on disk/S3, DB holds only the path)

# import sqlalchemy
# from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, Date, ForeignKey, UniqueConstraint
# from sqlalchemy.orm import sessionmaker, declarative_base
# from sqlalchemy.exc import IntegrityError
# from datetime import datetime
# import numpy as np
# import os
# import pickle  # to load .pkl encoding files

# # --- DATABASE CONFIGURATION ---
# DB_USER = "postgres"
# DB_PASSWORD = "aman"  # Your PostgreSQL password
# DB_HOST = "localhost"
# DB_PORT = "5432"
# DB_NAME = "attendance_system"

# # # --- DATABASE CONFIGURATION (RDS example) ---
# # DB_USER = "mlc_devdb_master"
# # DB_PASSWORD = "mc0RYjhPAfGhfaCHFDWX"
# # DB_HOST = "mlc-dev-db-pgsql-01.cdego6cy2f2o.ap-south-1.rds.amazonaws.com"
# # DB_PORT = "5432"
# # DB_NAME = "mlc_dev_db_01"

# DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()

# # Where .pkl encodings live locally during dev (S3 later).
# ENCODINGS_DIR = "enrollment_encodings"


# # --- FINAL TABLE DEFINITIONS ---
# class School(Base):
#     __tablename__ = "schools"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, unique=True, nullable=False)
#     last_student_serial = Column(Integer, default=0, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class Student(Base):
#     __tablename__ = "students"
#     id = Column(String, primary_key=True, index=True)
#     school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
#     name = Column(String, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class FaceEncoding(Base):
#     __tablename__ = "face_encodings"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     # NOTE: We are NOT storing encodings in DB anymore.
#     # Keep the column for backward compatibility; make it small/nullable.
#     encoding = Column(LargeBinary, nullable=True)  # legacy (unused now)
#     # We use this column to store the path to the .pkl encoding file (local or S3 URL).
#     image_path = Column(String, unique=True, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)

# class AttendanceLog(Base):
#     __tablename__ = "attendance_logs"
#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(String, ForeignKey('students.id'), nullable=False)
#     attendance_date = Column(Date, nullable=False)
#     first_seen_timestamp = Column(DateTime, nullable=False)
#     camera_id = Column(String)
#     # Keep name as-is to avoid migration surprises in existing DBs.
#     _table_args_ = (UniqueConstraint('student_id', 'attendance_date', name='_student_date_uc'),)


# # --- DB SESSION LIFECYCLE ---
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # --- DB INIT ---
# def create_database_and_tables():
#     try:
#         temp_engine = create_engine(
#             f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres",
#             isolation_level="AUTOCOMMIT"
#         )
#         with temp_engine.connect() as connection:
#             result = connection.execute(
#                 sqlalchemy.text(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
#             )
#             if not result.first():
#                 connection.execute(sqlalchemy.text(f'CREATE DATABASE "{DB_NAME}"'))
#                 print(f"Database '{DB_NAME}' created.")

#         Base.metadata.create_all(bind=engine)
#         print("Database and tables are ready.")

#     except Exception as e:
#         print(f"Error during database setup: {e}")
#         exit()

# create_database_and_tables()


# # --- SYNC HELPERS (dev/compat) ---
# def _ensure_school_and_student(db, school_id: int, student_name: str):
#     """Ensure School(id=school_id) and Student(name, school_id) exist; create if missing."""
#     # Ensure school exists
#     school = db.query(School).filter(School.id == school_id).first()
#     if not school:
#         school = School(id=school_id, name=f"School {school_id}")
#         db.add(school)
#         db.commit()
#         db.refresh(school)

#     # Ensure student exists or create new with serial
#     student = db.query(Student).filter(
#         Student.name == student_name, Student.school_id == school_id
#     ).first()
#     if not student:
#         # Lock/update school serial (simple version)
#         school_to_update = db.query(School).filter(School.id == school_id).with_for_update().one()
#         new_serial = school_to_update.last_student_serial + 1
#         new_student_id = f"{school_to_update.id}{new_serial:04d}"
#         school_to_update.last_student_serial = new_serial
#         student = Student(id=new_student_id, school_id=school_to_update.id, name=student_name)
#         db.add(student)
#         db.commit()
#     return student


# def sync_enrollment_data(db, encodings_root: str):
#     """
#     DEV/Compatibility: Scan encodings_root for .pkl files and register any that
#     aren't in the DB yet. Folder structure:
#         encodings_root/<school_id>/<student_name>/*.pkl
#     """
#     print("\n=== Synchronizing Encodings (.pkl) with Database ===")
#     os.makedirs(encodings_root, exist_ok=True)
#     synced_files = 0

#     for school_id_str in os.listdir(encodings_root):
#         school_folder_path = os.path.join(encodings_root, school_id_str)
#         if not os.path.isdir(school_folder_path):
#             continue
#         try:
#             school_id = int(school_id_str)
#         except ValueError:
#             continue

#         for student_name in os.listdir(school_folder_path):
#             student_folder_path = os.path.join(school_folder_path, student_name)
#             if not os.path.isdir(student_folder_path):
#                 continue

#             # Ensure entities exist
#             student = _ensure_school_and_student(db, school_id, student_name)

#             for filename in os.listdir(student_folder_path):
#                 if not filename.lower().endswith('.pkl'):
#                     continue
#                 file_path = os.path.join(student_folder_path, filename)

#                 # Skip if already registered
#                 exists = db.query(FaceEncoding).filter(
#                     FaceEncoding.image_path == file_path
#                 ).first()
#                 if exists:
#                     continue

#                 # Validate the pickle file is loadable (avoid registering broken files)
#                 try:
#                     with open(file_path, "rb") as f:
#                         _enc = pickle.load(f)
#                     # Register in DB with empty binary to minimize storage
#                     fe = FaceEncoding(student_id=student.id, encoding=b"", image_path=file_path)
#                     db.add(fe)
#                     synced_files += 1
#                 except Exception as e:
#                     print(f"  Skipping corrupt encoding file: {file_path} ({e})")

#     db.commit()
#     if synced_files > 0:
#         print(f"Sync complete. Added {synced_files} new encoding files.")
#     else:
#         print("Sync complete. No new encodings found.")


# # --- LOADER: used by API to load encodings into memory ---
# def load_known_faces_from_db(db):
#     """
#     Load encodings from file paths stored in DB (image_path now points to .pkl).
#     Returns: (known_face_encodings, known_face_student_ids, student_details_map)
#     """
#     print("Loading known faces from database (via .pkl paths)...")
#     rows = (
#         db.query(FaceEncoding, Student.name, Student.school_id)
#         .join(Student, FaceEncoding.student_id == Student.id)
#         .all()
#     )
#     if not rows:
#         return [], [], {}

#     encodings = []
#     student_ids = []
#     details = {}

#     missing = 0
#     unreadable = 0

#     for row in rows:
#         fe = row.FaceEncoding
#         student_name = row.name
#         school_id = row.school_id
#         path = fe.image_path

#         # Support local filesystem paths only here; S3 can be added later
#         if not path or not os.path.exists(path):
#             missing += 1
#             continue
#         try:
#             with open(path, "rb") as f:
#                 enc = pickle.load(f)  # numpy array
#             enc = np.asarray(enc, dtype=np.float64)
#             encodings.append(enc)
#             student_ids.append(fe.student_id)
#             details[fe.student_id] = {"name": student_name, "school_id": school_id}
#         except Exception:
#             unreadable += 1
#             continue

#     print(f"Loaded {len(encodings)} encodings. Missing: {missing}, Unreadable: {unreadable}.")
#     return encodings, student_ids, details


# # --- ATTENDANCE WRITE ---
# def mark_attendance(db, student_id, camera_id):
#     try:
#         db.add(
#             AttendanceLog(
#                 student_id=student_id,
#                 attendance_date=datetime.now().date(),
#                 first_seen_timestamp=datetime.now(),
#                 camera_id=str(camera_id),
#             )
#         )
#         db.commit()
#         return True
#     except IntegrityError:
#         db.rollback()
#         return False











#modify 2



import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import numpy as np
import os
import pickle

# --- DATABASE CONFIGURATION ---
DB_USER = "postgres"
DB_PASSWORD = "aman"  # Your PostgreSQL password
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "attendance_system"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Where .pkl encodings live locally.
ENCODINGS_DIR = "enrollment_encodings"


# --- TABLE DEFINITIONS ---
class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    last_student_serial = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Student(Base):
    __tablename__ = "students"
    id = Column(String, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FaceEncoding(Base):
    __tablename__ = "face_encodings"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey('students.id'), nullable=False)
    
    # **PROBLEM 2 SOLUTION**: This column is intentionally unused for storing encodings.
    # It is kept for backward compatibility but should always be empty.
    encoding = Column(LargeBinary, nullable=True)
    
    # **PROBLEM 2 SOLUTION**: This column stores the actual path to the .pkl file.
    image_path = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey('students.id'), nullable=False)
    attendance_date = Column(Date, nullable=False)
    first_seen_timestamp = Column(DateTime, nullable=False)
    camera_id = Column(String)
    
    # **PROBLEM 1 SOLUTION**: This constraint at the DB level prevents more than one
    # entry for the same student on the same date. This is the core of the fix.
    __table_args__ = (UniqueConstraint('student_id', 'attendance_date', name='_student_date_uc'),)


# --- DB SESSION LIFECYCLE ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- DB INIT ---
def create_database_and_tables():
    try:
        # Connect to the default 'postgres' database to check if our target DB exists
        temp_engine = create_engine(
            f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres",
            isolation_level="AUTOCOMMIT"
        )
        with temp_engine.connect() as connection:
            result = connection.execute(
                sqlalchemy.text(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
            )
            if not result.first():
                connection.execute(sqlalchemy.text(f'CREATE DATABASE "{DB_NAME}"'))
                print(f"Database '{DB_NAME}' created.")
        
        # Create all tables defined in this script on the target database engine.
        # This will apply the UniqueConstraint on the AttendanceLog table.
        Base.metadata.create_all(bind=engine)
        print("Database and tables are ready.")

    except Exception as e:
        print(f"Error during database setup: {e}")
        exit()

# Initialize the database and tables when this module is first imported.
create_database_and_tables()


# --- SYNC HELPERS ---
def _ensure_school_and_student(db, school_id: int, student_name: str):
    """Ensure School and Student exist; create if missing."""
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        school = School(id=school_id, name=f"School {school_id}")
        db.add(school)
        db.commit()
        db.refresh(school)

    student = db.query(Student).filter(
        Student.name == student_name, Student.school_id == school_id
    ).first()
    if not student:
        school_to_update = db.query(School).filter(School.id == school_id).with_for_update().one()
        new_serial = school_to_update.last_student_serial + 1
        new_student_id = f"{school_to_update.id}{new_serial:04d}"
        school_to_update.last_student_serial = new_serial
        student = Student(id=new_student_id, school_id=school_to_update.id, name=student_name)
        db.add(student)
        db.commit()
    return student


def sync_enrollment_data(db, encodings_root: str):
    """
    DEV/Compatibility: Scan encodings_root for .pkl files and register any that
    aren't in the DB yet. Folder structure:
        encodings_root/<school_id>/<student_name>/*.pkl
    """
    print("\n=== Synchronizing Encodings (.pkl) with Database ===")
    os.makedirs(encodings_root, exist_ok=True)
    synced_files = 0

    for school_id_str in os.listdir(encodings_root):
        school_folder_path = os.path.join(encodings_root, school_id_str)
        if not os.path.isdir(school_folder_path):
            continue
        try:
            school_id = int(school_id_str)
        except ValueError:
            continue

        for student_name in os.listdir(school_folder_path):
            student_folder_path = os.path.join(school_folder_path, student_name)
            if not os.path.isdir(student_folder_path):
                continue
            
            student = _ensure_school_and_student(db, school_id, student_name)

            for filename in os.listdir(student_folder_path):
                if not filename.lower().endswith('.pkl'):
                    continue
                file_path = os.path.join(student_folder_path, filename)
                
                exists = db.query(FaceEncoding).filter(
                    FaceEncoding.image_path == file_path
                ).first()
                if exists:
                    continue

                try:
                    with open(file_path, "rb") as f:
                        _enc = pickle.load(f)
                    fe = FaceEncoding(student_id=student.id, encoding=b"", image_path=file_path)
                    db.add(fe)
                    synced_files += 1
                except Exception as e:
                    print(f"  Skipping corrupt encoding file: {file_path} ({e})")

    db.commit()
    if synced_files > 0:
        print(f"Sync complete. Added {synced_files} new encoding files.")
    else:
        print("Sync complete. No new encodings found.")


# --- LOADER: used by API to load encodings into memory ---
def load_known_faces_from_db(db):
    """
    Load encodings from file paths stored in DB (image_path now points to .pkl).
    """
    print("Loading known faces from database (via .pkl paths)...")
    rows = (
        db.query(FaceEncoding, Student.name, Student.school_id)
        .join(Student, FaceEncoding.student_id == Student.id)
        .all()
    )
    if not rows:
        return [], [], {}

    encodings, student_ids, details = [], [], {}
    missing, unreadable = 0, 0

    for row in rows:
        path = row.FaceEncoding.image_path
        if not path or not os.path.exists(path):
            missing += 1
            continue
        try:
            with open(path, "rb") as f:
                enc = pickle.load(f)
            enc = np.asarray(enc, dtype=np.float64)
            encodings.append(enc)
            student_ids.append(row.FaceEncoding.student_id)
            details[row.FaceEncoding.student_id] = {"name": row.name, "school_id": row.school_id}
        except Exception:
            unreadable += 1
            continue

    print(f"Loaded {len(encodings)} encodings. Missing: {missing}, Unreadable: {unreadable}.")
    return encodings, student_ids, details


# --- ATTENDANCE WRITE ---
def mark_attendance(db, student_id, camera_id) -> bool:
    """
    Tries to log attendance. Returns True on success, False if already marked today.
    """
    try:
        db.add(
            AttendanceLog(
                student_id=student_id,
                attendance_date=datetime.now().date(),
                first_seen_timestamp=datetime.now(),
                camera_id=str(camera_id),
            )
        )
        db.commit()
        return True
    except IntegrityError:
        # This exception is raised by the DB when the UniqueConstraint is violated.
        db.rollback()
        return False