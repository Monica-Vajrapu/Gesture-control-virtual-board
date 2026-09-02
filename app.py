from flask import Flask, render_template, request, jsonify, url_for
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import base64
from hand_tracker import HandTracker
import time
import os
import uuid
from werkzeug.utils import secure_filename

try:
    import win32com.client
    import pythoncom
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SLIDES_FOLDER'] = os.path.join('static', 'slides')

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SLIDES_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

tracker = HandTracker(detection_con=0.8)

# State for presentation controls to prevent spamming
last_gesture_time = 0
cooldown_period = 1.0  # seconds

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify(success=False, error="No file part")
    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, error="No selected file")
    
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], unique_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, filename)
    file.save(file_path)
    
    # Absolute paths are required for COM
    abs_file_path = os.path.abspath(file_path)
    output_folder = os.path.join(os.path.abspath(app.config['SLIDES_FOLDER']), unique_id)
    os.makedirs(output_folder, exist_ok=True)
    
    if not HAS_WIN32COM:
        return jsonify(success=False, error="PowerPoint/Word conversion via MS Office COM is only supported when running locally on Windows.")
    
    slides = []
    try:
        pythoncom.CoInitialize()
        if filename.endswith(('.pptx', '.ppt')):
            slides = convert_ppt_to_images(abs_file_path, output_folder)
        elif filename.endswith(('.docx', '.doc')):
            slides = convert_word_to_images(abs_file_path, output_folder)
        else:
            return jsonify(success=False, error="Unsupported file type")
        
        # Convert internal paths to URLs
        slide_urls = [url_for('static', filename=f'slides/{unique_id}/{s}') for s in slides]
        return jsonify(success=True, slides=slide_urls)
    except Exception as e:
        print(f"Conversion error: {e}")
        return jsonify(success=False, error=str(e))
    finally:
        pythoncom.CoUninitialize()

def convert_ppt_to_images(file_path, output_folder):
    if not HAS_WIN32COM:
        raise Exception("Win32COM is not available on this operating system.")
    powerpoint = win32com.client.Dispatch("PowerPoint.Application")
    ppt = powerpoint.Presentations.Open(file_path, WithWindow=False)
    # 17 = ppSaveAsJPG
    ppt.SaveAs(output_folder, 17)
    ppt.Close()
    powerpoint.Quit()
    
    # Get list of images and sort them
    images = [f for f in os.listdir(output_folder) if f.endswith('.JPG')]
    images.sort(key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
    return images

def convert_word_to_images(file_path, output_folder):
    if not HAS_WIN32COM:
        raise Exception("Win32COM is not available on this operating system.")
    word = win32com.client.Dispatch("Word.Application")
    doc = word.Documents.Open(file_path)
    doc.Close()
    word.Quit()
    raise Exception("Word conversion currently requires additional libraries. Please use PPTX for now.")

@socketio.on('image')
def handle_image(data):
    # Decode the base64 image from the frontend
    encoded_data = data.split(',')[1]
    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Flip the image horizontally for a later selfie-view display
    img = cv2.flip(img, 1)
    
    # Process hand landmarks
    img = tracker.find_hands(img, draw=False)
    lm_list = tracker.find_position(img, draw=False)
    
    gesture = "NONE"
    coords = None
    
    if len(lm_list) != 0:
        fingers = tracker.fingers_up()
        gesture = tracker.get_gesture(fingers)
        
        # System-level controls for PPT/Word with cooldown
        global last_gesture_time
        current_time = time.time()
        
        discrete_gestures = ["SWIPE_LEFT", "SWIPE_RIGHT"]
        if HAS_PYAUTOGUI and gesture in discrete_gestures and (current_time - last_gesture_time > cooldown_period):
            try:
                if gesture == "SWIPE_LEFT":
                    pyautogui.press('right')
                elif gesture == "SWIPE_RIGHT":
                    pyautogui.press('left')
            except Exception as pe:
                print(f"PyAutoGUI simulation error: {pe}")
            last_gesture_time = current_time
            
        # Tracking tip of index finger (ID 8)
        coords = {"x": lm_list[8][1], "y": lm_list[8][2]}

    # Emit the results back to the frontend
    emit('response', {
        'gesture': gesture,
        'coords': coords
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
