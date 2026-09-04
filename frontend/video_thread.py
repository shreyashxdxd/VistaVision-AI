import sys
import time
import os
import cv2
import numpy as np
import requests
# pyrefly: ignore [missing-import]
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QImage

# Try to import YOLO defensively, so it doesn't fail import if still installing
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class VideoThread(QThread):
    # Signals
    frame_ready = Signal(QImage, list, dict)  # Emits (processed_frame, detections_list, stats_dict)
    alert_triggered = Signal(dict)           # Emits alert details (type, camera, message, timestamp)
    log_message = Signal(str, str, str)       # Emits (timestamp, message, level/color)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mutex = QMutex()
        self.running = False
        
        # Camera sources
        self.source = 0  # 0 for webcam, string for video filepath, 'simulation' for simulated feed
        self.source_changed = False
        
        # Display modes: 'normal', 'thermal', 'night', 'fence'
        self.display_mode = 'normal'
        self.fence_enabled = True
        self.recording_enabled = True
        
        # Integration mode: 'local' (runs YOLO in thread) or 'api' (sends to uvicorn)
        self.inference_engine = 'local' 
        
        # Load YOLO model locally if available
        self.yolo_model = None
        self.face_cascade = None
        self.load_models()

        # Optimization variables for FPS control
        self.frame_counter = 0
        self.last_detections = []
        self.last_faces = []
        self.skip_frames = 1

        # Position tracking history for action explanation
        self.position_history = {}
        
        # Keep track of active objects for alert analysis
        self.first_seen = {}       # track_id -> time.time()
        self.alerted_ids = set()    # track_id that already triggered intrusion alert
        self.loitering_alerted = set()  # track_id that already triggered loitering alert
        
        # Mapping track_id to license plates for simulated ANPR
        self.plates_map = {}
        self.plate_letters = ["DL", "MH", "HR", "KA", "JK", "UP"]
        
        # Simulation variables (used if source == 'simulation' or camera fails)
        self.simulated_entities = [
            {"id": 1, "class": "person", "x": 100, "y": 200, "speed_x": 4, "speed_y": 1},
            {"id": 2, "class": "car", "x": 1200, "y": 480, "speed_x": -12, "speed_y": 0},
            {"id": 3, "class": "person", "x": 400, "y": 150, "speed_x": 2, "speed_y": 2},
            {"id": 4, "class": "truck", "x": -200, "y": 520, "speed_x": 8, "speed_y": 0}
        ]

    def load_models(self):
        # Load YOLO model
        if YOLO_AVAILABLE:
            try:
                # Load yolo11n.pt if it exists in the workspace
                model_path = "yolo11n.pt"
                if not os.path.exists(model_path):
                    # Check in parent directories
                    model_path = "../yolo11n.pt"
                    if not os.path.exists(model_path):
                        model_path = "yolo11n.pt"  # Let it download automatically if needed
                
                self.yolo_model = YOLO(model_path)
                print(f"YOLO model loaded successfully from {model_path}.")
            except Exception as e:
                print(f"Error loading YOLO model: {e}. Falling back to simulation/API mode.")
                self.yolo_model = None
        else:
            print("YOLO/Ultralytics is not available. Local inference will fall back to simulation.")

        # Load Haar Cascade for face detection
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            if self.face_cascade.empty():
                self.face_cascade = None
                print("Warning: Face cascade could not be loaded.")
        except Exception as e:
            print(f"Error loading Face Cascade: {e}")
            self.face_cascade = None

    def set_source(self, source):
        with QMutexLocker(self.mutex):
            self.source = source
            self.source_changed = True
            
            # Reset tracking states on source change
            self.first_seen.clear()
            self.alerted_ids.clear()
            self.loitering_alerted.clear()
            self.plates_map.clear()
            self.position_history.clear()

    def set_display_mode(self, mode):
        with QMutexLocker(self.mutex):
            self.display_mode = mode

    def set_fence_enabled(self, enabled):
        with QMutexLocker(self.mutex):
            self.fence_enabled = enabled

    def set_recording_enabled(self, enabled):
        with QMutexLocker(self.mutex):
            self.recording_enabled = enabled

    def set_inference_engine(self, engine):
        with QMutexLocker(self.mutex):
            self.inference_engine = engine

    def get_timestamp(self):
        return time.strftime("%H:%M:%S")

    def run(self):
        self.running = True
        
        # Force initial load of self.source
        self.mutex.lock()
        self.source_changed = True
        self.mutex.unlock()
        
        cap = None
        source_val = None
        is_simulated = False
        fps = 30.0
        frame_delay = 1.0 / fps
        
        while self.running:
            # Check if source changed
            self.mutex.lock()
            change_triggered = self.source_changed
            if change_triggered:
                source_val = self.source
                self.source_changed = False
            self.mutex.unlock()
            
            if change_triggered:
                if cap is not None:
                    cap.release()
                    cap = None
                
                is_simulated = (source_val == 'simulation')
                if not is_simulated:
                    # Attempt to open camera/video
                    # If source is digit, convert to int (webcam index)
                    if isinstance(source_val, str) and source_val.isdigit():
                        cap_source = int(source_val)
                    elif isinstance(source_val, str):
                        is_stream = any(source_val.lower().startswith(proto) for proto in ["rtsp://", "rtmp://", "http://", "https://"])
                        if is_stream:
                            cap_source = source_val
                        else:
                            # Resolve path relative to script directory to be CWD-independent
                            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            if source_val.startswith('assets/') or source_val.startswith('assets\\'):
                                cap_source = os.path.normpath(os.path.join(script_dir, source_val))
                            else:
                                cap_source = os.path.normpath(os.path.abspath(source_val))
                    else:
                        cap_source = source_val
                    
                    # Log attempt
                    try:
                        with open("startup_debug.log", "a") as f:
                            f.write(f"[{self.get_timestamp()}] Attempting to open source: {cap_source}\n")
                    except:
                        pass
                    
                    # Check if local file exists before opening to prevent indefinite hang
                    if isinstance(cap_source, str) and not any(cap_source.lower().startswith(proto) for proto in ["rtsp://", "rtmp://", "http://", "https://"]):
                        if not os.path.exists(cap_source):
                            try:
                                with open("startup_debug.log", "a") as f:
                                    f.write(f"[{self.get_timestamp()}] Error: Local file not found: {cap_source}. Trying fallback to sample video...\n")
                            except:
                                pass
                            
                            # Fallback check
                            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            fallback_source = os.path.normpath(os.path.join(script_dir, "assets", "sample_video.mp4"))
                            if os.path.exists(fallback_source):
                                cap_source = fallback_source
                            else:
                                is_simulated = True
                                
                    if not is_simulated:
                        cap = cv2.VideoCapture(cap_source)
                        
                        # Double fallback if CCTV video failed to load (e.g. codec issue)
                        if not cap.isOpened() and "15474594" in str(cap_source):
                            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            fallback_source = os.path.normpath(os.path.join(script_dir, "assets", "sample_video.mp4"))
                            try:
                                with open("startup_debug.log", "a") as f:
                                    f.write(f"[{self.get_timestamp()}] Warning: Primary video codec failed. Trying fallback: {fallback_source}\n")
                            except:
                                pass
                            cap = cv2.VideoCapture(fallback_source)
                            if cap.isOpened():
                                cap_source = fallback_source
                                
                        if not cap.isOpened():
                            try:
                                with open("startup_debug.log", "a") as f:
                                    f.write(f"[{self.get_timestamp()}] Error: Could not open source {cap_source}. Falling back to simulation.\n")
                            except:
                                pass
                            is_simulated = True
                            cap = None
                        else:
                            try:
                                with open("startup_debug.log", "a") as f:
                                    f.write(f"[{self.get_timestamp()}] Success: Opened source {cap_source}\n")
                            except:
                                pass
                            native_fps = cap.get(cv2.CAP_PROP_FPS)
                            if native_fps > 0 and native_fps < 120:
                                fps = native_fps
                            else:
                                fps = 30.0
                            frame_delay = 1.0 / fps

            # Read frame
            loop_start = time.time()
            frame = None
            if is_simulated:
                frame = self.generate_simulated_frame()
                time.sleep(0.033) # Simulate 30 FPS
            else:
                ret, frame = cap.read()
                if not ret:
                    # Loop video if it is a file
                    if isinstance(source_val, str):
                        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        test_path = os.path.join(script_dir, source_val) if (source_val.startswith('assets/') or source_val.startswith('assets\\')) else source_val
                        if os.path.exists(test_path) or os.path.exists(source_val):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                    
                    try:
                        with open("startup_debug.log", "a") as f:
                            f.write(f"[{self.get_timestamp()}] Error: Lost frame connection for {source_val}. Falling back to simulation.\n")
                    except:
                        pass
                    is_simulated = True
                    continue

            # Process the frame
            processed_frame, detections, stats = self.process_frame(frame, is_simulated)
            
            # Convert to QImage and emit
            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            rgb_frame = np.ascontiguousarray(rgb_frame)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            q_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # We emit a copy of QImage to prevent memory access issues across threads
            self.frame_ready.emit(q_image.copy(), detections, stats)
            
            # Throttle FPS for video files
            if not is_simulated:
                elapsed = time.time() - loop_start
                sleep_time = frame_delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
        if cap is not None:
            cap.release()

    def stop(self):
        self.running = False
        self.wait()

    def generate_simulated_frame(self):
        # Create a dark gray canvas
        width, height = 1280, 720
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)  # Charcoal background
        
        # Draw background grids
        for x in range(0, width, 100):
            cv2.line(frame, (x, 0), (x, height), (40, 40, 40), 1)
        for y in range(0, height, 100):
            cv2.line(frame, (0, y), (width, y), (40, 40, 40), 1)
            
        # Draw a road layout
        cv2.rectangle(frame, (0, 450), (width, 680), (50, 50, 50), -1)
        cv2.line(frame, (0, 450), (width, 450), (100, 100, 100), 2)
        cv2.line(frame, (0, 680), (width, 680), (100, 100, 100), 2)
        # Road lane markers
        for x in range(0, width, 80):
            cv2.line(frame, (x, 565), (x + 40, 565), (255, 255, 255), 2)
            
        # Draw a checkpoint gate area
        cv2.rectangle(frame, (600, 300), (680, 450), (80, 80, 80), -1)
        cv2.putText(frame, "POST 01", (610, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # Border boundary wall line (simulated fence barrier)
        cv2.line(frame, (0, 400), (600, 400), (70, 70, 70), 5)
        cv2.line(frame, (680, 400), (width, 400), (70, 70, 70), 5)
        
        # Draw simulated entities moving
        for ent in self.simulated_entities:
            # Update coordinate
            ent["x"] += ent["speed_x"]
            ent["y"] += ent["speed_y"]
            
            # Wrap around boundaries
            if ent["speed_x"] > 0 and ent["x"] > width + 100:
                ent["x"] = -100
                ent["id"] += 4 # Assign new ID
            elif ent["speed_x"] < 0 and ent["x"] < -100:
                ent["x"] = width + 100
                ent["id"] += 4
                
            if ent["speed_y"] > 0 and ent["y"] > height + 50:
                ent["y"] = -50
            elif ent["speed_y"] < 0 and ent["y"] < -50:
                ent["y"] = height + 50

            # Draw shapes onto the simulated frame to represent entities
            color = (0, 255, 0) if ent["class"] == "person" else (255, 200, 0)
            if ent["class"] == "person":
                # Draw pedestrian
                cv2.circle(frame, (int(ent["x"]), int(ent["y"])), 15, color, -1)
                cv2.line(frame, (int(ent["x"]), int(ent["y"] + 15)), (int(ent["x"]), int(ent["y"] + 45)), color, 3)
            else:
                # Draw vehicle shape
                cv2.rectangle(frame, (int(ent["x"] - 50), int(ent["y"] - 25)), (int(ent["x"] + 50), int(ent["y"] + 25)), color, -1)
                # Wheels
                cv2.circle(frame, (int(ent["x"] - 30), int(ent["y"] + 25)), 8, (10, 10, 10), -1)
                cv2.circle(frame, (int(ent["x"] + 30), int(ent["y"] + 25)), 8, (10, 10, 10), -1)

        return frame

    def process_frame(self, frame, is_simulated):
        # Resize to standard size (e.g. 1280x720) for consistent overlays
        h, w = frame.shape[:2]
        if w != 1280 or h != 720:
            frame = cv2.resize(frame, (1280, 720))
            w, h = 1280, 720

        detections = []
        self.mutex.lock()
        engine = self.inference_engine
        self.mutex.unlock()
        
        # 1. Run AI Detections (Local YOLO or Simulated or API)
        if is_simulated:
            detections = self.get_simulated_detections()
        else:
            self.frame_counter += 1
            if self.frame_counter % self.skip_frames == 0:
                t0 = time.time()
                if engine == 'local' and self.yolo_model is not None:
                    self.last_detections = self.run_local_yolo(frame)
                elif engine == 'api':
                    self.last_detections = self.run_api_detect(frame)
                else:
                    # Fallback to local YOLO if uvicorn is down, or local simulation
                    if self.yolo_model is not None:
                        self.last_detections = self.run_local_yolo(frame)
                    else:
                        self.last_detections = self.get_simulated_detections()
                
                inference_time = time.time() - t0
                # Dynamically adjust skip_frames based on inference time
                # If target is 30 FPS (~33ms per frame), choose skip_frames to not drop below 25-30 FPS
                if inference_time > 0.033:
                    self.skip_frames = min(10, max(1, int(inference_time / 0.033)))
                else:
                    self.skip_frames = 1
            
            detections = self.last_detections.copy() if self.last_detections else []

        # 2. Run Face Detection
        faces_detected = 0
        if self.face_cascade is not None:
            if is_simulated:
                pass
            elif self.frame_counter % self.skip_frames == 0:
                self.last_faces = []
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray_small = cv2.resize(gray, (640, 360))
                faces = self.face_cascade.detectMultiScale(gray_small, 1.1, 4)
                for (fx, fy, fw, fh) in faces:
                    # Scale boxes back to 1280x720
                    fx1, fy1, fx2, fy2 = fx * 2, fy * 2, (fx + fw) * 2, (fy + fh) * 2
                    self.last_faces.append({
                        "class": "face",
                        "confidence": 0.82,
                        "box": [fx1, fy1, fx2, fy2],
                        "track_id": None
                    })
            
            if not is_simulated:
                for face_det in self.last_faces:
                    detections.append(face_det.copy())
                    faces_detected += 1

        # 3. Analytics Counts & Alerts Analysis
        stats = {
            "humans": 0,
            "vehicles": 0,
            "faces": faces_detected,
            "plates": 0,
            "alerts": 0,
            "phones": 0
        }
        
        now = time.time()
        active_alert_message = None
        
        # Virtual Fence coordinates (horizontal line across the checkpoint boundary)
        # Represented as line from (0, 420) to (1280, 420)
        fence_y = 420
        
        processed_detections = []
        
        for det in detections:
            cls = det["class"]
            conf = det["confidence"]
            x1, y1, x2, y2 = [int(v) for v in det["box"]]
            tid = det.get("track_id")
            
            # Count statistics
            if cls == "person":
                stats["humans"] += 1
            elif cls in ["car", "truck", "bus", "motorcycle", "bicycle"]:
                stats["vehicles"] += 1
            elif cls == "cell phone":
                stats["phones"] += 1
            elif cls == "face":
                pass
                
            # Perform Simulated ANPR on Vehicles
            anpr_text = None
            if cls in ["car", "truck", "bus"] and tid is not None:
                stats["plates"] += 1
                if tid not in self.plates_map:
                    # Generate a consistent fake license plate
                    prefix = np.random.choice(self.plate_letters)
                    state_num = f"{np.random.randint(10, 99)}"
                    letters = f"{chr(np.random.randint(65, 90))}{chr(np.random.randint(65, 90))}"
                    num = f"{np.random.randint(1000, 9999)}"
                    self.plates_map[tid] = f"{prefix} {state_num} {letters} {num}"
                    
                    # Emit log message for plate detection
                    self.log_message.emit(
                        self.get_timestamp(),
                        f"ANPR | Vehicle #{tid:02d} plate read: {self.plates_map[tid]}",
                        "info"
                    )
                anpr_text = self.plates_map[tid]
            
            # Tracking & Suspicious Loitering Logic
            is_suspicious = False
            if tid is not None:
                if tid not in self.first_seen:
                    self.first_seen[tid] = now
                    # Emit normal discovery log
                    self.log_message.emit(
                        self.get_timestamp(),
                        f"Tracking | {cls.capitalize()} #{tid:02d} detected in zone",
                        "normal"
                    )
                else:
                    duration = now - self.first_seen[tid]
                    if duration > 8.0:  # Loitered for more than 8 seconds
                        is_suspicious = True
                        if tid not in self.loitering_alerted:
                            self.loitering_alerted.add(tid)
                            msg = f"SUSPICIOUS | {cls.capitalize()} #{tid:02d} loitering in restricted sector (>8s)"
                            self.log_message.emit(self.get_timestamp(), msg, "warning")
                            self.alert_triggered.emit({
                                "type": "LOITERING ALERT",
                                "camera": f"Camera 0{1 if self.source==0 else 2}",
                                "message": msg,
                                "timestamp": self.get_timestamp(),
                                "level": "MEDIUM"
                            })
            
            # Virtual Fence Crossing Logic
            is_intrusion = False
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            
            self.mutex.lock()
            fence_chk = self.fence_enabled
            self.mutex.unlock()
            
            # Intrusion occurs if crossing below fence boundary (cy > fence_y)
            if fence_chk and cy > fence_y:
                is_intrusion = True
                if tid is not None and tid not in self.alerted_ids:
                    self.alerted_ids.add(tid)
                    msg = f"INTRUSION | {cls.capitalize()} #{tid:02d} crossed Virtual Fence boundary!"
                    self.log_message.emit(self.get_timestamp(), msg, "critical")
                    
                    self.alert_triggered.emit({
                        "type": "INTRUSION DETECTED",
                        "camera": f"Camera 0{1 if self.source==0 else 2}",
                        "message": msg,
                        "timestamp": self.get_timestamp(),
                        "level": "HIGH"
                    })
                    active_alert_message = msg

            # Calculate dynamic action explanation for persons
            explanation = []
            if cls == "person":
                if tid is not None:
                    history = self.position_history.setdefault(tid, [])
                    history.append((cx, cy, now))
                    if len(history) > 20:
                        history.pop(0)
                        
                    if len(history) >= 5:
                        x0, y0, t0 = history[0]
                        xn, yn, tn = history[-1]
                        dt = tn - t0
                        if dt > 0.15:
                            dist = ((xn - x0)**2 + (yn - y0)**2)**0.5
                            speed = dist / dt
                            
                            if is_intrusion:
                                state = "INTRUDER"
                                explanation = [
                                    f"ALERT: {state} | FENCE CROSS",
                                    f"SPEED: {speed*0.05:.2f} m/s | INTRUSION HIGH"
                                ]
                            elif is_suspicious:
                                state = "LOITERING"
                                explanation = [
                                    f"WARN: {state} | REPEATED DWELL",
                                    "STATUS: SUSPICIOUS ACTIVITY PATTERN"
                                ]
                            elif speed > 25.0:
                                state = "WALKING"
                                dx = xn - x0
                                dy = yn - y0
                                if abs(dx) > abs(dy):
                                    dir_str = "Moving East" if dx > 0 else "Moving West"
                                else:
                                    dir_str = "Southbound" if dy > 0 else "Northbound"
                                explanation = [
                                    f"STATE: {state} | {dir_str.upper()}",
                                    f"SPEED: {speed*0.05:.2f} m/s (ACTIVE TRACK)"
                                ]
                            else:
                                state = "STOPPED"
                                explanation = [
                                    f"STATE: {state} | STATIONARY",
                                    "STATUS: ASSESSING ZONE PERIMETER"
                                ]
                        else:
                            explanation = [
                                "STATE: UNIDENTIFIED | CALIBRATING",
                                "STATUS: ACQUIRING MOTION SIGNALS"
                            ]
                    else:
                        explanation = [
                            "STATE: UNIDENTIFIED | CALIBRATING",
                            "STATUS: ACQUIRING MOTION SIGNALS"
                        ]
                else:
                    explanation = [
                        "STATE: UNIDENTIFIED | NO TRACK",
                        "STATUS: TRANSIENT TARGET DETECTION"
                    ]
            
            # Save processed data
            det_copy = det.copy()
            det_copy["anpr"] = anpr_text
            det_copy["loitering"] = is_suspicious
            det_copy["intrusion"] = is_intrusion
            det_copy["explanation"] = explanation
            processed_detections.append(det_copy)

        # Draw overlays on the BGR frame based on the active Display Mode
        self.mutex.lock()
        mode = self.display_mode
        draw_fence = self.fence_enabled
        rec_on = self.recording_enabled
        self.mutex.unlock()

        # Apply visual modes (Shaders/Filters)
        out_frame = frame.copy()
        if mode == 'thermal':
            # Create a thermal vision effect
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Boost brightness for heat look
            gray = cv2.equalizeHist(gray)
            out_frame = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
        elif mode == 'night':
            # Create a night vision green-tint effect
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Brighten slightly
            gray = cv2.add(gray, 40)
            green_channel = gray
            # Merge: green boosted, red and blue minimized
            red_blue = np.zeros_like(gray)
            out_frame = cv2.merge([red_blue, green_channel, red_blue])
            
            # Add random digital scanning noise
            noise = np.random.randint(0, 15, out_frame.shape, dtype=np.uint8)
            out_frame = cv2.add(out_frame, noise)
            
            # Add horizontal scanlines
            for y in range(0, 720, 4):
                cv2.line(out_frame, (0, y), (1280, y), (0, 10, 0), 1)

        # Draw Virtual Fence line overlay
        if draw_fence:
            # Flashing line color if alert is active
            if active_alert_message is not None or (int(time.time() * 2) % 2 == 0 and len(self.alerted_ids) > 0):
                fence_color = (0, 0, 255) # Bright Alert Red
                fence_thickness = 4
            else:
                fence_color = (0, 255, 0) # Safety Green
                fence_thickness = 2
            
            cv2.line(out_frame, (0, fence_y), (1280, fence_y), fence_color, fence_thickness)
            cv2.putText(out_frame, "RESTRICTED BOUNDARY - SECURE LINE", (20, fence_y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, fence_color, 2)

        # Draw Bounding Boxes and IDs on the final processed frame
        for det in processed_detections:
            cls = det["class"]
            conf = det["confidence"]
            x1, y1, x2, y2 = [int(v) for v in det["box"]]
            tid = det.get("track_id")
            anpr = det.get("anpr")
            is_susp = det.get("loitering")
            is_intr = det.get("intrusion")

            # Determine colors: Red for Intrusion, Orange for Suspicious, Green for Normal, Yellow for Faces
            if is_intr:
                box_color = (0, 0, 255)  # Red
            elif is_susp:
                box_color = (0, 140, 255) # Orange/Amber
            elif cls == "face":
                box_color = (0, 255, 255) # Yellow
            else:
                box_color = (0, 255, 0)   # Green

            # Bounding box
            cv2.rectangle(out_frame, (x1, y1), (x2, y2), box_color, 2)
            
            # Construct text label
            label = f"{cls.upper()}"
            if tid is not None:
                label += f" #{tid:02d}"
            label += f" [{int(conf*100)}%]"
            
            if anpr:
                label += f" | PLATE: {anpr}"
                
            # Draw label box
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(out_frame, (x1, y1 - 20), (x1 + lw + 10, y1), box_color, -1)
            cv2.putText(out_frame, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
            
            # If there is an explanation, draw it below the box
            explanation = det.get("explanation")
            if explanation:
                line1, line2 = explanation
                ey = y2 + 5
                # draw line 1
                (lw1, lh1), _ = cv2.getTextSize(line1, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                cv2.rectangle(out_frame, (x1, ey), (x1 + max(lw1 + 10, 160), ey + lh1 + 6), (15, 15, 15), -1)
                cv2.rectangle(out_frame, (x1, ey), (x1 + max(lw1 + 10, 160), ey + lh1 + 6), box_color, 1)
                cv2.putText(out_frame, line1, (x1 + 5, ey + lh1 + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 1)
                
                # draw line 2
                ey2 = ey + lh1 + 8
                (lw2, lh2), _ = cv2.getTextSize(line2, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
                cv2.rectangle(out_frame, (x1, ey2), (x1 + max(lw2 + 10, 160), ey2 + lh2 + 6), (15, 15, 15), -1)
                cv2.rectangle(out_frame, (x1, ey2), (x1 + max(lw2 + 10, 160), ey2 + lh2 + 6), (100, 100, 100), 1)
                cv2.putText(out_frame, line2, (x1 + 5, ey2 + lh2 + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)

        # Draw Premium HUD interface (surveillance metrics)
        # Top banner info
        cv2.rectangle(out_frame, (0, 0), (1280, 45), (15, 15, 15), -1)
        cv2.putText(out_frame, f"CAM: 01 (CHECKPOINT S1)   |   FPS: 30   |   ENGINE: {mode.upper()}   |   AI: {engine.upper()}", 
                    (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        
        # Live flashing indicator
        if int(time.time()) % 2 == 0:
            cv2.circle(out_frame, (1230, 23), 6, (0, 255, 0), -1)
            cv2.putText(out_frame, "LIVE", (1180, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            cv2.circle(out_frame, (1230, 23), 6, (0, 100, 0), -1)
            cv2.putText(out_frame, "LIVE", (1180, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 180, 0), 1)

        # Draw Recording Indicator
        if rec_on:
            cv2.rectangle(out_frame, (20, 60), (110, 90), (15, 15, 15), -1)
            cv2.putText(out_frame, "REC", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            if int(time.time() * 2) % 2 == 0:
                cv2.circle(out_frame, (35, 78), 5, (0, 0, 255), -1)

        # Update stats alert counter
        stats["alerts"] = len(self.alerted_ids) + len(self.loitering_alerted)

        return out_frame, processed_detections, stats

    def run_local_yolo(self, frame):
        """
        Runs YOLO model locally in the worker thread.
        """
        if self.yolo_model is None:
            return []
            
        detections = []
        try:
            # Classes: 0:person, 1:bicycle, 2:car, 3:motorcycle, 5:bus, 7:truck, 67:cell phone
            results = self.yolo_model.track(
                frame,
                imgsz=640,
                conf=0.35,
                classes=[0, 1, 2, 3, 5, 7, 67],
                persist=True,
                verbose=False
            )
            
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0].item())
                    
                    class_mapping = {
                        0: "person", 1: "bicycle", 2: "car",
                        3: "motorcycle", 5: "bus", 7: "truck",
                        67: "cell phone"
                    }
                    class_name = class_mapping.get(cls_id, "unknown")
                    track_id = int(box.id[0].item()) if box.id is not None else None
                    
                    detections.append({
                        "class": class_name,
                        "confidence": conf,
                        "box": [x1, y1, x2, y2],
                        "track_id": track_id
                    })
        except Exception as e:
            print(f"Local YOLO track error: {e}")
        return detections

    def run_api_detect(self, frame):
        """
        Sends frame to FastAPI /detect endpoint.
        """
        detections = []
        try:
            # Compress frame to JPEG
            _, img_encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            files = {'file': ('frame.jpg', img_encoded.tobytes(), 'image/jpeg')}
            
            response = requests.post("http://127.0.0.1:8000/detect", files=files, timeout=3.0)
            if response.status_code == 200:
                data = response.json()
                detections = data.get("detections", [])
        except Exception as e:
            # If server fails, silently log/return empty to avoid crashing thread
            pass
        return detections

    def get_simulated_detections(self):
        """
        Generates simulated YOLO detections matching the positions of the simulated entities.
        """
        detections = []
        for ent in self.simulated_entities:
            eid = ent["id"]
            cls = ent["class"]
            ex = ent["x"]
            ey = ent["y"]
            
            # Map center coordinate to bounding box
            if cls == "person":
                x1, y1 = ex - 15, ey
                x2, y2 = ex + 15, ey + 60
            else: # vehicle
                x1, y1 = ex - 60, ey - 30
                x2, y2 = ex + 60, ey + 35
                
            detections.append({
                "class": cls,
                "confidence": 0.85 + (eid % 10) * 0.01,
                "box": [x1, y1, x2, y2],
                "track_id": eid
            })
        return detections
