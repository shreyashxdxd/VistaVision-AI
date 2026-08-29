const camera = document.getElementById("camera");
const canvas = document.getElementById("detectionCanvas");

const startCameraButton =
    document.getElementById("startCamera");

const snapshotButton =
    document.getElementById("snapshotButton");

const analysisButton =
    document.getElementById("analysisButton");

const snapshot =
    document.getElementById("snapshot");

const snapshotPlaceholder =
    document.getElementById("snapshotPlaceholder");

const cameraMessage =
    document.getElementById("cameraMessage");

const analysisResult =
    document.getElementById("analysisResult");

const analysisStatus =
    document.getElementById("analysisStatus");


// Canvas used ONLY for YOLO frame capture
const frameCanvas =
    document.createElement("canvas");

const frameContext =
    frameCanvas.getContext("2d");

// Canvas used ONLY for drawing boxes
const detectionContext =
    canvas.getContext("2d");


let stream = null;
let detectionRunning = false;
let detectionBusy = false;

let lastDetectionTime = 0;


// =========================================================
// START CAMERA
// =========================================================

startCameraButton.addEventListener(
    "click",
    async () => {

        try {

            stream =
                await navigator.mediaDevices.getUserMedia({
                    video: {
                        width: {
                            ideal: 1280
                        },
                        height: {
                            ideal: 720
                        }
                    },
                    audio: false
                });

            camera.srcObject = stream;

            await camera.play();

            cameraMessage.style.display =
                "none";

            startCameraButton.disabled =
                true;

            snapshotButton.disabled =
                false;


            // Set overlay dimensions
            canvas.width =
                camera.videoWidth;

            canvas.height =
                camera.videoHeight;


            // Small resolution for YOLO
            frameCanvas.width = 640;
            frameCanvas.height = 360;


            detectionRunning = true;

            requestAnimationFrame(
                detectionLoop
            );


        } catch (error) {

            console.error(error);

            cameraMessage.textContent =
                "Unable to access camera.";

        }

    }
);


// =========================================================
// DETECTION LOOP
// =========================================================

function detectionLoop(timestamp) {

    if (!detectionRunning) {
        return;
    }


    /*
        Run detection only every 350ms.

        That's roughly:
        1000 / 350 ≈ 2.8 FPS

        The CAMERA itself remains 30 FPS.
    */

    if (
        timestamp - lastDetectionTime > 350 &&
        !detectionBusy
    ) {

        lastDetectionTime =
            timestamp;

        runDetection();
    }


    requestAnimationFrame(
        detectionLoop
    );
}


// =========================================================
// SEND LOW-RES FRAME TO YOLO
// =========================================================

async function runDetection() {

    if (
        !camera.videoWidth ||
        !camera.videoHeight
    ) {
        return;
    }


    detectionBusy = true;


    try {

        // Capture small frame
        frameContext.drawImage(
            camera,
            0,
            0,
            frameCanvas.width,
            frameCanvas.height
        );


        const blob =
            await new Promise(resolve => {

                frameCanvas.toBlob(
                    resolve,
                    "image/jpeg",
                    0.65
                );

            });


        const formData =
            new FormData();


        formData.append(
            "file",
            blob,
            "frame.jpg"
        );


        const response =
            await fetch(
                "http://127.0.0.1:8000/detect",
                {
                    method: "POST",
                    body: formData
                }
            );


        if (!response.ok) {
            throw new Error(
                "YOLO request failed"
            );
        }


        const data =
            await response.json();


        drawDetections(
            data.detections,
            data.width,
            data.height
        );


    } catch (error) {

        console.error(
            "Detection error:",
            error
        );

    } finally {

        detectionBusy = false;

    }
}


// =========================================================
// DRAW DETECTIONS
// =========================================================

function drawDetections(
    detections,
    sourceWidth,
    sourceHeight
) {

    // Clear previous boxes
    detectionContext.clearRect(
        0,
        0,
        canvas.width,
        canvas.height
    );


    const scaleX =
        canvas.width / sourceWidth;

    const scaleY =
        canvas.height / sourceHeight;


    detections.forEach(
        detection => {

            const [
                x1,
                y1,
                x2,
                y2
            ] = detection.box;


            const boxX =
                x1 * scaleX;

            const boxY =
                y1 * scaleY;

            const boxWidth =
                (x2 - x1) * scaleX;

            const boxHeight =
                (y2 - y1) * scaleY;


            const confidence =
                (
                    detection.confidence * 100
                ).toFixed(1);


            const label =
                `PERSON ${confidence}%`;


            // Bounding box
            detectionContext.strokeStyle =
                "#38bdf8";

            detectionContext.lineWidth = 3;

            detectionContext.strokeRect(
                boxX,
                boxY,
                boxWidth,
                boxHeight
            );


            // Label
            detectionContext.font =
                "bold 14px Arial";


            const textWidth =
                detectionContext
                    .measureText(label)
                    .width;


            detectionContext.fillStyle =
                "#38bdf8";


            detectionContext.fillRect(
                boxX,
                Math.max(0, boxY - 27),
                textWidth + 14,
                27
            );


            detectionContext.fillStyle =
                "#061016";


            detectionContext.fillText(
                label,
                boxX + 7,
                Math.max(19, boxY - 8)
            );

        }
    );
}


// =========================================================
// SNAPSHOT
// =========================================================

snapshotButton.addEventListener(
    "click",
    () => {

        if (!stream) return;


        const snapshotCanvas =
            document.createElement(
                "canvas"
            );


        snapshotCanvas.width =
            camera.videoWidth;

        snapshotCanvas.height =
            camera.videoHeight;


        const snapshotContext =
            snapshotCanvas.getContext(
                "2d"
            );


        snapshotContext.drawImage(
            camera,
            0,
            0,
            snapshotCanvas.width,
            snapshotCanvas.height
        );


        const imageData =
            snapshotCanvas.toDataURL(
                "image/jpeg",
                0.9
            );


        snapshot.src =
            imageData;


        snapshot.style.display =
            "block";


        snapshotPlaceholder.style.display =
            "none";


        analysisButton.disabled =
            false;


        analysisStatus.textContent =
            "READY";


        analysisResult.innerHTML = `
            <p>
                Incident captured successfully.
                Press <strong>AI ANALYSIS</strong>
                to analyze the image.
            </p>
        `;

    }
);

// =========================================================
// AI ANALYSIS
// =========================================================

analysisButton.addEventListener(
    "click",
    async () => {

        if (!snapshot.src) {
            return;
        }


        analysisButton.disabled = true;

        analysisStatus.textContent =
            "ANALYZING";


        analysisResult.innerHTML = `
            <p>
                🤖 AI is analyzing the incident...
            </p>
        `;


        try {

            // Convert snapshot data URL to Blob
            const response =
                await fetch(snapshot.src);

            const blob =
                await response.blob();


            // Prepare form data
            const formData =
                new FormData();

            formData.append(
                "file",
                blob,
                "incident.jpg"
            );


            // Send to FastAPI
            const aiResponse =
                await fetch(
                    "http://127.0.0.1:8000/analyze",
                    {
                        method: "POST",
                        body: formData
                    }
                );


            const data =
                await aiResponse.json();


            if (!data.success) {
                throw new Error(
                    data.error ||
                    "AI analysis failed"
                );
            }


            // Display result
            analysisStatus.textContent =
                "COMPLETE";


            analysisResult.innerHTML =
                formatAIResponse(
                    data.analysis
                );


        } catch (error) {

            console.error(
                "AI analysis error:",
                error
            );


            analysisStatus.textContent =
                "ERROR";


            analysisResult.innerHTML = `
                <p>
                    ⚠️ Unable to analyze
                    the incident.
                </p>

                <p>
                    ${error.message}
                </p>
            `;


        } finally {

            analysisButton.disabled =
                false;

        }

    }
);

function formatAIResponse(text) {

    return text
        .replace(
            /\*\*(.*?)\*\*/g,
            "<strong>$1</strong>"
        )
        .replace(
            /^(PEOPLE|ENVIRONMENT|POTENTIAL HAZARDS|POSSIBLE CONCERNS|RECOMMENDED ATTENTION)$/gm,
            "<strong class=\"ai-section\">$1</strong>"
        )
        .replace(/\n/g, "<br>");
}