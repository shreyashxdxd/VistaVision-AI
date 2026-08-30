# VistaVision AI

VistaVision AI is a real-time computer vision prototype designed to assist in emergency and rescue scenarios.

The system uses a live camera feed to detect people using YOLO and allows the user to capture a snapshot of an incident. The captured image can then be analyzed by an AI vision model to provide useful visual insights about the scene.

## Features

- Real-time camera feed
- Real-time human detection using YOLO
- Live bounding boxes around detected people
- Incident snapshot capture
- AI-powered image analysis
- Analysis of people, environment, visible hazards, and potential concerns

## How It Works

```
Live Camera
     ↓
YOLO Human Detection
     ↓
Live Bounding Boxes
     ↓
Capture Snapshot
     ↓
AI Vision Analysis
     ↓
AI Insights
```

## Tech Stack

- Python
- FastAPI
- YOLO Algorithm
- AI API (Gemini in this case)
- HTML
- CSS
- JavaScript

## Project Structure

```
VistaVision AI/
│
├── backend/
│   └── main.py
│
├── front-end/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── yolo11n.pt
├── .gitignore
└── README.md
```

## Running the Project

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/VistaVision-AI.git
cd VistaVision
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\ctivate
```

### 3. Install dependencies

```bash
pip install fastapi uvicorn ultralytics pillow google-genai python-dotenv python-multipart
```

### 4. Add your Gemini API key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

### 5. Start the backend

```bash
python -m uvicorn backend.main:app --reload
```

The backend will run at:

http://(Port number here)

### 6. Start the frontend

Open:

front-end/index.html

in your browser.

Allow camera access when prompted.

## Usage

1. Start the camera.
2. The system detects people in real time.
3. Bounding boxes appear around detected people.
4. Capture an incident snapshot.
5. Click **AI Analysis**.
6. The AI analyzes the captured image and displays the results.

## Disclaimer

This is a prototype intended for demonstration and development purposes.

AI analysis is based only on visible information in the captured image and should not be treated as a definitive assessment of an emergency, injury, or rescue situation.

## Future Improvements

- Real-time object and hazard detection
- Fire and smoke detection
- Improved emergency classification
- Location/GPS integration
- Multiple camera support
- Real-time alerts
- Deployment on drones and edge devices
- Improved detection performance

---

**VistaVision AI — Prototype V1.0**