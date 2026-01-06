



import cv2
import requests
import time
import threading
import os

# --- CONFIGURATION ---
# IMPORTANT: Change this to your EC2 server's public IP address or domain name
API_URL = "http://127.0.0.1:8000/attendance/mark" 
# The ID for this specific camera client
CAMERA_ID = "MainGateCam_01"
# Time to wait between sending frames to the API (in seconds)
PROCESS_INTERVAL = 2

# Define your camera sources here. Use 0 for a local webcam for testing.
CAMERA_SOURCES = {
    "Test_Webcam": 0,
    # "MainGate_Cam": "rtsp://user:pass@192.168.1.101:554/stream1",
}

def camera_worker(camera_id, source):
    """
    A dedicated function that runs in a thread for a single camera.
    It captures and sends frames to the API at a regular interval.
    """
    print(f"[{camera_id}] Starting thread for camera source: {source}")
    video_capture = cv2.VideoCapture(source)
    last_process_time = 0

    while True:
        if not video_capture.isOpened():
            print(f"[{camera_id}] Error connecting to camera. Retrying in 10 seconds...")
            time.sleep(10)
            video_capture = cv2.VideoCapture(source)
            continue

        ret, frame = video_capture.read()
        if not ret:
            print(f"[{camera_id}] No frame received. Reconnecting...")
            video_capture.release()
            time.sleep(5)
            video_capture = cv2.VideoCapture(source)
            continue

        # Check if it's time to process and send this frame
        if time.time() - last_process_time > PROCESS_INTERVAL:
            last_process_time = time.time()
            
            _, img_encoded = cv2.imencode('.jpg', frame)
            files = {'image': ('frame.jpg', img_encoded.tobytes(), 'image/jpeg')}
            payload = {'camera_id': camera_id}
            
            print(f"[{camera_id}] Sending frame to API for recognition...")
            try:
                # Send the request to your main API on AWS
                response = requests.post(API_URL, files=files, data=payload, timeout=10)
                print(f"[{camera_id}] API Response: {response.json()}")
            except requests.exceptions.RequestException as e:
                print(f"[{camera_id}] Error connecting to API: {e}")
        
        # Display the live video feed for debugging
        cv2.imshow(f"{camera_id} - Live Feed", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    video_capture.release()
    cv2.destroyAllWindows()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    threads = []
    for camera_id, url in CAMERA_SOURCES.items():
        thread = threading.Thread(target=camera_worker, args=(camera_id, url))
        threads.append(thread)
        thread.start()
        time.sleep(1)

    for thread in threads:
        thread.join()

    print("All camera client threads have finished.")




























































# # central_client.py (Final Version with Liveness Check)
# import os
# import cv2
# import requests
# import time
# import threading
# import dlib
# from imutils import face_utils
# from scipy.spatial import distance
# import face_recognition # We use this for a quick face location check

# # --- CONFIGURATION ---
# API_URL = "http://127.0.0.1:8000/attendance/mark"
# PROCESS_INTERVAL = 2 # Seconds to wait after a successful send
# EAR_THRESHOLD = 0.2
# CONSEC_FRAMES = 2

# CAMERA_URLS = {
#     "MainGate_Cam": "rtsp://user:pass@192.168.1.101:554/stream1",
#     # Use 0 for your local webcam for testing
#     "Test_Webcam": 0, 
# }

# # --- DLIB and Liveness Setup ---
# print("Loading dlib facial landmark predictor...")
# if not os.path.exists("shape_predictor_68_face_landmarks.dat"):
#     print("Error: 'shape_predictor_68_face_landmarks.dat' not found.")
#     exit()
# predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
# detector = dlib.get_frontal_face_detector()
# (lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
# (rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

# def eye_aspect_ratio(eye):
#     denom = distance.euclidean(eye[0], eye[3])
#     return (distance.euclidean(eye[1], eye[5]) + distance.euclidean(eye[2], eye[4])) / (2.0 * denom) if denom != 0 else 0.3

# def camera_worker(camera_id, source):
#     """A dedicated function that performs liveness check and sends frames to the API."""
#     print(f"[{camera_id}] Starting thread for camera source: {source}")
#     video_capture = cv2.VideoCapture(source)
#     blink_counter = 0

#     while True:
#         if not video_capture.isOpened():
#             print(f"[{camera_id}] Error connecting to camera. Retrying...")
#             time.sleep(10)
#             video_capture = cv2.VideoCapture(source)
#             continue

#         ret, frame = video_capture.read()
#         if not ret:
#             print(f"[{camera_id}] No frame received. Reconnecting...")
#             video_capture.release()
#             time.sleep(5)
#             video_capture = cv2.VideoCapture(source)
#             continue
            
#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#         rects = detector(gray, 0) # Use dlib to find faces for liveness check

#         for rect in rects:
#             shape = predictor(gray, rect)
#             shape_np = face_utils.shape_to_np(shape)
#             ear = (eye_aspect_ratio(shape_np[lStart:lEnd]) + eye_aspect_ratio(shape_np[rStart:rEnd])) / 2.0

#             if ear < EAR_THRESHOLD:
#                 blink_counter += 1
#             else:
#                 if blink_counter >= CONSEC_FRAMES:
#                     print(f"[{camera_id}] Liveness confirmed (blink detected)!")
                    
#                     # A person blinked, now send this frame to the API for recognition
#                     _, img_encoded = cv2.imencode('.jpg', frame)
#                     files = {'image': ('frame.jpg', img_encoded.tobytes(), 'image/jpeg')}
#                     payload = {'camera_id': camera_id}
                    
#                     try:
#                         response = requests.post(API_URL, files=files, data=payload, timeout=10)
#                         print(f"[{camera_id}] API Response: {response.json()}")
#                     except requests.exceptions.RequestException as e:
#                         print(f"[{camera_id}] Error connecting to API: {e}")
                    
#                     # Wait for a few seconds before trying to detect again for this camera
#                     time.sleep(PROCESS_INTERVAL)
                
#                 blink_counter = 0 # Reset counter if eyes are open

#         # Optional: Display the local video feed for debugging
#         cv2.imshow(f"{camera_id} - Live Feed", frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     video_capture.release()
#     cv2.destroyAllWindows()

# # --- MAIN EXECUTION ---
# if __name__ == "__main__":
#     threads = []
#     for camera_id, url in CAMERA_URLS.items():
#         thread = threading.Thread(target=camera_worker, args=(camera_id, url))
#         threads.append(thread)
#         thread.start()
#         time.sleep(1)

#     for thread in threads:
#         thread.join()

#     print("All camera threads have finished.")



































# # # central_client.py
# # import cv2
# # import requests
# # import time
# # import threading

# # # --- CONFIGURATION ---
# # API_URL = "http://<your-aws-ec2-ip-address>:8000/attendance/mark"
# # PROCESS_INTERVAL = 2 # Seconds between sending a frame from each camera

# # # List all your camera stream URLs here
# # CAMERA_URLS = {
# #     "MainGate_Cam": "rtsp://user:pass@192.168.1.101:554/stream1",
# #     "Library_Cam": "rtsp://user:pass@192.168.1.102:554/stream1",
# #     # Add more cameras with unique names here
# # }

# # def camera_worker(camera_id, rtsp_url):
# #     """
# #     A dedicated function that runs in a thread for a single camera.
# #     """
# #     print(f"[{camera_id}] Starting thread for camera at {rtsp_url}")
# #     video_capture = cv2.VideoCapture(rtsp_url)
# #     last_process_time = 0

# #     while True:
# #         if not video_capture.isOpened():
# #             print(f"[{camera_id}] Error: Could not connect to camera. Retrying in 10 seconds...")
# #             time.sleep(10)
# #             video_capture = cv2.VideoCapture(rtsp_url)
# #             continue

# #         ret, frame = video_capture.read()
# #         if not ret:
# #             print(f"[{camera_id}] No frame received. Reconnecting...")
# #             video_capture.release()
# #             time.sleep(5)
# #             video_capture = cv2.VideoCapture(rtsp_url)
# #             continue

# #         # Check if it's time to process and send this frame
# #         if time.time() - last_process_time > PROCESS_INTERVAL:
# #             last_process_time = time.time()
            
# #             _, img_encoded = cv2.imencode('.jpg', frame)
# #             files = {'image': ('frame.jpg', img_encoded.tobytes(), 'image/jpeg')}
# #             payload = {'camera_id': camera_id}
            
# #             print(f"[{camera_id}] Sending frame to API...")
# #             try:
# #                 # Send the request to your main API on AWS
# #                 response = requests.post(API_URL, files=files, data=payload, timeout=10)
# #                 print(f"[{camera_id}] API Response: {response.json()}")
# #             except requests.exceptions.RequestException as e:
# #                 print(f"[{camera_id}] Error connecting to API: {e}")
        
# #         # A small sleep to prevent this thread from using 100% CPU
# #         time.sleep(0.01)

# # # --- MAIN EXECUTION ---
# # if __name__ == "__main__":
# #     threads = []
# #     for camera_id, url in CAMERA_URLS.items():
# #         # Create one thread per camera
# #         thread = threading.Thread(target=camera_worker, args=(camera_id, url))
# #         threads.append(thread)
# #         thread.start() # Start the thread
# #         time.sleep(1) # Stagger camera startups

# #     # Keep the main script running while threads are active
# #     for thread in threads:
# #         thread.join()

# #     print("All camera threads have finished.")



