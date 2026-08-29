from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from ultralytics import YOLO

from PIL import Image

from google import genai
from google.genai import types

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

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found in .env"
    )

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)

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

    # Only detect PERSON
    results = model(
        image,
        imgsz=640,
        conf=0.35,
        classes=[0],
        verbose=False
    )

    detections = []

    for result in results:

        for box in result.boxes:

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            confidence = float(box.conf[0])

            detections.append({
                "class": "person",
                "confidence": confidence,
                "box": [
                    x1,
                    y1,
                    x2,
                    y2
                ]
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


    try:

        interaction = gemini_client.interactions.create(

            model="gemini-3.6-flash",

            input=[
                {
                    "type": "text",
                    "text": prompt
                },

                {
                    "type": "image",
                    "data": image_base64,
                    "mime_type": "image/jpeg"
                }
            ]
        )


        return {
            "success": True,
            "analysis": interaction.output_text
        }


    except Exception as e:

        print("Gemini error:", e)

        return {
            "success": False,
            "error": str(e)
        }