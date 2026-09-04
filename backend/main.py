from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from ultralytics import YOLO

from PIL import Image

from google import genai

from dotenv import load_dotenv

import io
import os
import base64


app = FastAPI(title="Rescue Vision AI")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )
else:
    print("WARNING: GEMINI_API_KEY not found. AI visual analysis features (/analyze) will be disabled.")

# Load model once
model = YOLO("yolo11n.pt")


@app.get("/")
def root():
    return {
        "status": "online",
        "message": "Rescue Vision AI backend is running"
    }


@app.post("/detect")
async def detect(file: UploadFile = File(...)):

    image_bytes = await file.read()

    image = Image.open(
        io.BytesIO(image_bytes)
    ).convert("RGB")

    # Detect person (0), bicycle (1), car (2), motorcycle (3), bus (5), truck (7), cell phone (67)
    classes_to_detect = [0, 1, 2, 3, 5, 7, 67]
    class_mapping = {
        0: "person",
        1: "bicycle",
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
        67: "cell phone"
    }

    # Run YOLO with tracking support
    results = model.track(
        image,
        imgsz=640,
        conf=0.35,
        classes=classes_to_detect,
        persist=True,
        verbose=False
    )

    detections = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0])
            cls_id = int(box.cls[0].item())
            class_name = class_mapping.get(cls_id, "unknown")
            
            # Get track ID if available
            track_id = int(box.id[0].item()) if box.id is not None else None

            detections.append({
                "class": class_name,
                "confidence": confidence,
                "box": [x1, y1, x2, y2],
                "track_id": track_id
            })

    return {
        "detections": detections,
        "width": image.width,
        "height": image.height
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):

    image_bytes = await file.read()

    image_base64 = base64.b64encode(
        image_bytes
    ).decode("utf-8")


    prompt = """
You are an AI visual analysis assistant for a
rescue and emergency-response system.

Analyze the provided image carefully.

Provide a concise assessment using these sections:

PEOPLE
- Number of visible people.
- What they appear to be doing.
- Their apparent position or condition.

ENVIRONMENT
- Describe the relevant surroundings.

POTENTIAL HAZARDS
- Identify visible hazards such as fire, smoke,
  water, debris, vehicles, dangerous terrain,
  structural damage, or other risks.

POSSIBLE CONCERNS
- Identify anything unusual that may require
  attention or further investigation.

RECOMMENDED ATTENTION
- Classify the scene as:
  No action required
  POTENTIALLY CONCERNING
  or
  POTENTIALLY URGENT

IMPORTANT:
- Only describe things that are actually visible.
- Do not invent injuries or events.
- Clearly distinguish observations from uncertainty.
- Do not make medical diagnoses.
- Keep the response concise and structured.
"""


    if not gemini_client:
        return {
            "success": False,
            "error": "Gemini API key is not configured. Please set GEMINI_API_KEY in .env"
        }

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                image,
                prompt
            ]
        )

        return {
            "success": True,
            "analysis": response.text
        }


    except Exception as e:

        print("Gemini error:", e)

        return {
            "success": False,
            "error": str(e)
        }