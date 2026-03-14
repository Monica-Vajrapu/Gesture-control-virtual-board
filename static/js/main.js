const socket = io();

// UI Elements
const video = document.getElementById('webcam');
const whiteboard = document.getElementById('whiteboard');
const ctx = whiteboard.getContext('2d');
const gestureText = document.getElementById('current-gesture');
const clearBtn = document.getElementById('clear-btn');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('doc-upload');
const slideNav = document.getElementById('slide-nav');
const slideInfo = document.getElementById('slide-info');

// State
let currentColor = '#000000';
let lastCoords = null;
let slides = [];
let currentSlideIndex = 0;

// Initialize Canvas
function resizeCanvas() {
    whiteboard.width = window.innerWidth;
    whiteboard.height = window.innerHeight - document.querySelector('header').offsetHeight;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.lineWidth = 5;
    // Don't clear with white if we have slides, the background will show the slide
}

function clearCanvas() {
    ctx.clearRect(0, 0, whiteboard.width, whiteboard.height);
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// Webcam Setup
async function setupWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        return new Promise((resolve) => {
            video.onloadedmetadata = () => {
                resolve(video);
            };
        });
    } catch (err) {
        console.error("Error accessing webcam: ", err);
    }
}

// Processing Loop
function captureFrame() {
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = video.videoWidth;
    tempCanvas.height = video.videoHeight;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

    const dataUrl = tempCanvas.toDataURL('image/jpeg', 0.5);
    socket.emit('image', dataUrl);
}

// Socket Response
socket.on('response', (data) => {
    const { gesture, coords } = data;
    gestureText.innerText = gesture;

    if (coords) {
        // Map backend coords (usually 640x480 or similar) to frontend canvas
        const x = (coords.x / video.videoWidth) * whiteboard.width;
        const y = (coords.y / video.videoHeight) * whiteboard.height;
        handleGesture(gesture, x, y);
    } else {
        lastCoords = null;
    }

    requestAnimationFrame(captureFrame);
});

const colors = ['#000000', '#FF0000', '#00FF00', '#0000FF', '#FFFF00'];
let colorIndex = 0;
let lastActionTime = 0;
const COOLDOWN = 1000; // 1 second

function handleGesture(gesture, x, y) {
    const now = Date.now();
    const isDiscrete = ['CLEAR', 'COLOR', 'SWIPE_LEFT', 'SWIPE_RIGHT'].includes(gesture);

    if (isDiscrete && (now - lastActionTime < COOLDOWN)) {
        return;
    }

    if (gesture === 'DRAW') {
        ctx.strokeStyle = currentColor;
        ctx.lineWidth = 5;
        draw(x, y);
    } else if (gesture === 'ERASE') {
        ctx.globalCompositeOperation = 'destination-out';
        ctx.lineWidth = 50;
        draw(x, y);
        ctx.globalCompositeOperation = 'source-over';
    } else if (gesture === 'CLEAR') {
        clearCanvas();
        lastCoords = null;
        lastActionTime = now;
    } else if (gesture === 'COLOR') {
        colorIndex = (colorIndex + 1) % colors.length;
        currentColor = colors[colorIndex];
        lastCoords = null;
        lastActionTime = now;
    } else if (gesture === 'SWIPE_LEFT') {
        nextSlide();
        lastActionTime = now;
    } else if (gesture === 'SWIPE_RIGHT') {
        prevSlide();
        lastActionTime = now;
    } else {
        lastCoords = null;
    }

    gestureText.setAttribute('data-last', gesture);
}

function draw(x, y) {
    if (lastCoords) {
        ctx.beginPath();
        ctx.moveTo(lastCoords.x, lastCoords.y);
        ctx.lineTo(x, y);
        ctx.stroke();
    }
    lastCoords = { x, y };
}

// Slide Navigation
function updateSlide() {
    if (slides.length > 0) {
        whiteboard.style.backgroundImage = `url(${slides[currentSlideIndex]})`;
        slideInfo.innerText = `Slide ${currentSlideIndex + 1}/${slides.length}`;
        clearCanvas(); // Clear drawings when changing slides
    }
}

function nextSlide() {
    if (currentSlideIndex < slides.length - 1) {
        currentSlideIndex++;
        updateSlide();
    }
}

function prevSlide() {
    if (currentSlideIndex > 0) {
        currentSlideIndex--;
        updateSlide();
    }
}

// Upload Handling
uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.innerText = 'Uploading...';
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            slides = data.slides;
            currentSlideIndex = 0;
            slideNav.classList.remove('hidden');
            updateSlide();
        } else {
            alert('Upload failed: ' + data.error);
        }
    } catch (err) {
        console.error(err);
        alert('Error uploading file');
    } finally {
        uploadBtn.innerText = 'Upload Doc';
    }
});

// Event Listeners
clearBtn.addEventListener('click', clearCanvas);

const helpBtn = document.getElementById('help-btn');
const helpPanel = document.getElementById('guide-panel');
const closeHelpBtn = document.getElementById('close-guide');

helpBtn.addEventListener('click', () => {
    helpPanel.classList.toggle('hidden');
});

closeHelpBtn.addEventListener('click', () => {
    helpPanel.classList.add('hidden');
});

// Start
setupWebcam().then(() => {
    captureFrame();
});
