from flask import Flask, render_template, Response, request, redirect, url_for, jsonify, flash, send_file
from flask_cors import CORS
import cv2
import os
import pickle
import face_recognition
import numpy as np
import EncodeGenerator
import json
import io
from datetime import datetime

app = Flask(__name__)
CORS(app)
app.secret_key = 'supersecretkey'  # Needed for flash messages

UPLOAD_FOLDER = 'uploads'
USER_DATA_FILE = 'user_data.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# WEB CAM VIDEO CAPTURE
camera = cv2.VideoCapture(0)

# LOADING ENCODED FILE AND SAVE IT AS A PICKLE FILE
print("Loading Encoded File...")
file = open('Encodefile.p', 'rb')
encodeListKnownWithIds = pickle.load(file)
file.close()

encodeListKnown, studentIds = encodeListKnownWithIds
print("Encoded file loaded...")

user_db = {
    "sayantan": "10000"
}

# Global variable to track face recognition
face_recognized = False

# Dictionary to store room deadlines
room_deadlines = {}

def generate_frames():
    global face_recognized
    while True:
        # read the camera frame
        success, frame = camera.read()
        if not success:
            break
        else:
            imgS = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
            imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

            faceCurFrame = face_recognition.face_locations(imgS)
            encodeCurFrame = face_recognition.face_encodings(imgS, faceCurFrame)

            if faceCurFrame:
                for encodeFace, faceloc in zip(encodeCurFrame, faceCurFrame):
                    matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
                    faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)

                    matchIndex = np.argmin(faceDis)
                    if matches[matchIndex]:
                        print(studentIds[matchIndex])
                        face_recognized = True

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        form_values = request.form.to_dict()
        userName = form_values["userName"]
        userId = form_values["userID"]
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                user_data = json.load(f)
        else:
            user_data = {}

        if userId in user_data and userName == user_data.get(userId, None):
            return render_template('index.html')
        else:
            flash('Not a valid userID or Name. Provide details properly', 'error')
            return redirect('/login')

    return redirect('/login')

@app.route('/host/<room_id>/<user_id>', methods=['GET'])
def host(room_id, user_id):
    deadline_str = request.args.get('deadline')
    if deadline_str:
        deadline = datetime.fromisoformat(deadline_str)
        room_deadlines[room_id] = deadline
        return redirect(f'http://localhost:5000/host/{room_id}/{user_id}')
    else:
        return "Deadline not provided", 400

@app.route('/user/<room_id>/<user_id>', methods=['GET'])
def user(room_id, user_id):
    deadline = room_deadlines.get(room_id)
    if deadline:
        if datetime.now() <= deadline:
            return redirect(f'http://localhost:5000/user/{room_id}/{user_id}')
        else:
            return "Joining deadline has passed", 403
    else:
        return "Room not found or deadline not set", 404

@app.route('/upload', methods=['POST'])
def upload_file():
    form_values = request.form.to_dict()
    user_id = form_values["user_id"]
    user_name = form_values["user_name"]

    if 'image' not in request.files:
        return 'No file part'

    file = request.files['image']

    if file.filename == '':
        return 'No selected file'

    if file:
        # Save user data to JSON file
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                user_data = json.load(f)
        else:
            user_data = {}
        if not user_data.get(user_id, None):
            user_data[user_id] = user_name
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_id + ".png")
            file.save(file_path)
            EncodeGenerator.encodeGenerator()

            with open(USER_DATA_FILE, 'w') as f:
                json.dump(user_data, f)

            # Generate the file to be downloaded
            
            return redirect('/login')
           
    return 'File upload failed'

@app.route('/download/<user_id>/<pwd>')
def download(user_id, pwd):
     user_info = f"Username: {pwd}\nUser ID: {user_id}"
     return send_file(io.BytesIO(user_info.encode()), as_attachment=True, download_name=f'{pwd}_credentials.txt', mimetype='text/plain')

@app.route('/getUserName/<user_id>')
def getUserName(user_id):
    with open(USER_DATA_FILE, 'r') as f:
        db = json.load(f)
        return {"username":db.get(user_id, "Not Found")}

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/classes')
def classes():
    return render_template('classes.html')

@app.route('/login')
def login():
    return render_template('login.html')

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

if __name__ == "__main__":
    app.run(debug=True)
