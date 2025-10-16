from flask import Flask, render_template, Response, request, redirect, url_for, jsonify, flash, send_file
from flask_cors import CORS
import cv2
import os
import face_recognition
import numpy as np
import json
import io
from datetime import datetime
from EncodeGenerator import encode_and_store_faces
import chromadb
from chromadb.config import Settings


app = Flask(__name__)
CORS(app)

app.secret_key = 'supersecretkey'

UPLOAD_FOLDER = 'uploads'
USER_DATA_FILE = 'user_data.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


chroma_client = chromadb.PersistentClient(path="chroma_db")
collection = chroma_client.get_or_create_collection(name="face_encodings")

camera = cv2.VideoCapture(0)
face_recognized = False
room_deadlines = {}

#  Query ChromaDB for face match
def recognize_face_vector(query_encoding):
    results = collection.query(
        query_embeddings=[query_encoding.tolist()],
        n_results=1
    )
    if results and results['metadatas'][0]:
        return results['metadatas'][0][0], results['distances'][0][0]
    return None, None

#  Stream webcam and check face
def generate_frames():
    global face_recognized, recognized_user
    recognition_cooldown = False
    recognized_user = None  # Add this global variable to store matched user_id

    while True:
        success, frame = camera.read()
        if not success or frame is None:
            continue

        try:
            imgS = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
            imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)
        except cv2.error:
            continue

        faceCurFrame = face_recognition.face_locations(imgS)
        encodeCurFrame = face_recognition.face_encodings(imgS, faceCurFrame)

        if faceCurFrame and not recognition_cooldown:
            for encodeFace in encodeCurFrame:
                match_meta, distance = recognize_face_vector(encodeFace)

                print(" Checking match for current frame...")
                print("Distance:", distance)
                print("Metadata:", match_meta)

                if match_meta and distance < 0.35:
                    recognized_user = match_meta.get("user_id", "Unknown")
                    print(f"Face matched: {recognized_user} with distance {distance}")
                    face_recognized = True
                    recognition_cooldown = True
                else:
                    print("No face match or distance too high.")

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


# Encode and store uploaded face
def encode_new_face(user_id, user_name, image_path):
    image = cv2.imread(image_path)
    if image is None:
        print(f" Could not load image for {user_id}")
        return

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, boxes)

    if encodings:
        embedding = encodings[0].tolist()
        collection.add(
            ids=[user_id],
            embeddings=[embedding],
            metadatas=[{"user_id": user_id, "user_name": user_name}]
        )
        print(f" Stored encoding for {user_name} ({user_id})")
    else:
        print(f" No face detected in {user_id}'s image")

# Routes
@app.route('/')
def root_redirect():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    global face_recognized
    face_recognized = False  # Reset face status every login

    if request.method == 'POST':
        user_name = request.form.get("userName")
        user_id = request.form.get("userID")

        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                user_data = json.load(f)
        else:
            user_data = {}

        if user_id in user_data and user_name == user_data.get(user_id):
            return redirect('/index')
        else:
            flash("Invalid user ID or name", "danger")
            return redirect('/login')

    return render_template('login.html')

@app.route('/index')
def index_page():
    return render_template('index.html')

@app.route('/classes')
def classes():
    return render_template('classes.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        user_id = request.form.get("user_id")
        user_name = request.form.get("user_name")

        if 'image' not in request.files:
            return 'No file part'

        file = request.files['image']
        if file.filename == '':
            return 'No selected file'

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{user_id}.png")
        file.save(file_path)

        # Save user info
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                user_data = json.load(f)
        else:
            user_data = {}

        user_data[user_id] = user_name
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(user_data, f)

        # Encode to ChromaDB
        encode_new_face(user_id, user_name, file_path)
        return redirect('/login')

    return redirect('/signup')

@app.route('/download/<user_id>/<pwd>')
def download(user_id, pwd):
    user_info = f"Username: {pwd}\nUser ID: {user_id}"
    return send_file(io.BytesIO(user_info.encode()), as_attachment=True,
                     download_name=f'{pwd}_credentials.txt', mimetype='text/plain')

@app.route('/getUserName/<user_id>')
def get_user_name(user_id):
    with open(USER_DATA_FILE, 'r') as f:
        db = json.load(f)
    return {"username": db.get(user_id, "Not Found")}

@app.route('/video')
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/check_face')
def check_face():
    global face_recognized
    return jsonify({'recognized': face_recognized})

@app.route('/stop_camera')
def stop_camera():
    global camera
    camera.release()
    return jsonify({'status': 'camera stopped'})

@app.route('/host/<room_id>/<user_id>')
def host(room_id, user_id):
    deadline_str = request.args.get('deadline')
    if deadline_str:
        deadline = datetime.fromisoformat(deadline_str)
        room_deadlines[room_id] = deadline
        return redirect(f'/host/{room_id}/{user_id}')
    else:
        return "Deadline not provided", 400

@app.route('/user/<room_id>/<user_id>')
def user(room_id, user_id):
    deadline = room_deadlines.get(room_id)
    if deadline:
        if datetime.now() <= deadline:
            return redirect(f'/user/{room_id}/{user_id}')
        else:
            return "Joining deadline has passed", 403
    else:
        return "Room not found or deadline not set", 404


if __name__ == "__main__":
    encode_and_store_faces()
    app.run(debug=True)
