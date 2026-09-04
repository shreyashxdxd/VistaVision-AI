import sys
import time
import os
# pyrefly: ignore [missing-import]
from PySide6.QtCore import Qt, QTimer, QTime
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QImage, QPixmap, QFont
# pyrefly: ignore [missing-import]
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QListWidget, 
    QListWidgetItem, QTableWidget, QTableWidgetItem, 
    QFileDialog, QFrame, QSplitter, QHeaderView, QAbstractItemView,
    QInputDialog
)
from frontend.video_thread import VideoThread


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("IBVAP - Intelligent Border Video Analytics Platform")
        self.resize(1400, 850)
        self.setMinimumSize(1200, 750)
        
        # Load Premium Stylesheet (Cybersecurity/Tactical Operations Theme)
        self.apply_dark_theme()
        
        # Create and configure the background video processing thread
        self.video_thread = VideoThread()
        self.video_thread.frame_ready.connect(self.update_video_frame)
        self.video_thread.alert_triggered.connect(self.handle_alert)
        self.video_thread.log_message.connect(self.add_log_entry)
        
        # Build UI layout
        self.init_ui()
        
        # Start a clock timer for date/time update in header
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        
        # Start the video processing thread with a default video source (CCTV boundary feed)
        self.video_thread.set_source('vistavision/assets/cctv.mp4')
        self.video_thread.start()
        
        # Log startup
        self.add_log_entry(
            time.strftime("%H:%M:%S"),
            "System initialized. Monitoring strategic border checkpoints.",
            "info"
        )
        self.add_log_entry(
            time.strftime("%H:%M:%S"),
            "AI Core: YOLO Human/Vehicle tracking running in offline fallback mode.",
            "info"
        )

    def apply_dark_theme(self):
        stylesheet = """
        QMainWindow {
            background-color: #0d0e15;
        }
        QWidget {
            font-family: 'Segoe UI', 'Ubuntu', 'Helvetica', sans-serif;
            color: #d1d2d6;
        }
        QFrame {
            border: none;
        }
        /* Top Header Area */
        QWidget#headerPanel {
            background-color: #13141f;
            border-bottom: 2px solid #232533;
        }
        QLabel#headerTitle {
            color: #00d2ff;
            font-size: 20px;
            font-weight: bold;
            letter-spacing: 2px;
        }
        QLabel#headerClock {
            color: #8f929d;
            font-size: 14px;
            font-family: 'Consolas', monospace;
        }
        QLabel#statusDot {
            color: #00ff66;
            font-size: 16px;
        }
        QLabel#statusText {
            color: #00ff66;
            font-size: 13px;
            font-weight: bold;
            letter-spacing: 1px;
        }
        
        /* Sidebar Panels */
        QFrame#sidebarFrame {
            background-color: #13141f;
            border-radius: 6px;
            border: 1px solid #232533;
        }
        QLabel#sidebarTitle {
            color: #00d2ff;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 1px;
            padding: 8px;
            border-bottom: 1px solid #232533;
            background-color: #1a1b28;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
        }
        
        /* Camera List Widget */
        QListWidget#cameraList {
            background-color: transparent;
            border: none;
            outline: none;
            padding: 4px;
        }
        QListWidget#cameraList::item {
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 4px;
            border-left: 3px solid transparent;
            font-size: 13px;
        }
        QListWidget#cameraList::item:hover {
            background-color: #1e202f;
        }
        QListWidget#cameraList::item:selected {
            background-color: #23273e;
            color: #ffffff;
            border-left: 3px solid #00d2ff;
        }
        
        /* Alerts List Widget */
        QListWidget#alertsList {
            background-color: transparent;
            border: none;
            outline: none;
        }
        
        /* Video Control Buttons */
        QPushButton.controlBtn {
            background-color: #1a1b28;
            color: #8f929d;
            border: 1px solid #2c2f46;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 11px;
            letter-spacing: 1px;
        }
        QPushButton.controlBtn:hover {
            border-color: #00d2ff;
            color: #00d2ff;
            background-color: #1e2537;
        }
        QPushButton.controlBtn:checked {
            background-color: #00d2ff;
            color: #0d0e15;
            border-color: #00d2ff;
        }
        QPushButton.controlBtn:pressed {
            background-color: #00a2c7;
        }
        
        /* Tactical HUD indicators on Sidebars */
        QFrame#statWidget {
            background-color: #1a1b28;
            border-radius: 4px;
            border: 1px solid #232533;
            padding: 10px;
        }
        QLabel#statVal {
            color: #ffffff;
            font-size: 26px;
            font-weight: bold;
            font-family: 'Consolas', monospace;
        }
        QLabel#statLabel {
            color: #8f929d;
            font-size: 11px;
            text-transform: uppercase;
            font-weight: bold;
            letter-spacing: 1px;
        }
        
        /* Event Log Grid */
        QTableWidget#eventLogTable {
            background-color: #13141f;
            border: 1px solid #232533;
            border-radius: 6px;
            gridline-color: #1a1b28;
            font-family: 'Consolas', monospace;
            font-size: 12px;
        }
        QHeaderView::section {
            background-color: #1a1b28;
            color: #00d2ff;
            padding: 6px;
            border: 1px solid #232533;
            font-weight: bold;
            font-size: 11px;
            letter-spacing: 1px;
        }
        QTableWidget::item {
            padding: 6px;
        }
        
        /* Main Video Screen Container */
        QFrame#videoContainer {
            background-color: #08090d;
            border: 2px solid #232533;
            border-radius: 6px;
        }
        """
        self.setStyleSheet(stylesheet)

    def init_ui(self):
        # Main Layout is Vertical
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. HEADER BAR
        header = QWidget()
        header.setObjectName("headerPanel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)
        
        title_label = QLabel("IBVAP – INTELLIGENT BORDER VIDEO ANALYTICS PLATFORM")
        title_label.setObjectName("headerTitle")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Online Live indicators
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_text = QLabel("SYSTEM LIVE")
        self.status_text.setObjectName("statusText")
        
        self.clock_label = QLabel("")
        self.clock_label.setObjectName("headerClock")
        self.update_clock()
        
        header_layout.addWidget(self.status_dot)
        header_layout.addWidget(self.status_text)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.clock_label)
        
        main_layout.addWidget(header)
        
        # 2. WORKSPACE SPLITTER (Horizontal between Sidebar and Main Content)
        workspace_splitter = QSplitter(Qt.Horizontal)
        workspace_splitter.setHandleWidth(2)
        workspace_splitter.setStyleSheet("QSplitter::handle { background-color: #232533; }")
        
        # 2A. LEFT SIDEBAR - CAMERA PANEL
        left_panel = QFrame()
        left_panel.setObjectName("sidebarFrame")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        left_title = QLabel("CAMERA MANAGER")
        left_title.setObjectName("sidebarTitle")
        left_layout.addWidget(left_title)
        
        self.camera_list = QListWidget()
        self.camera_list.setObjectName("cameraList")
        
        # Populate demo camera list
        cam_1 = QListWidgetItem("● Camera 01 - Cam Realtime Detection")
        cam_1.setData(Qt.UserRole, "0") # Webcam 0
        
        cam_2 = QListWidgetItem("● Camera 02 - CCTV Boundary Feed")
        cam_2.setData(Qt.UserRole, "vistavision/assets/cctv.mp4") # CCTV video file
        
        cam_3 = QListWidgetItem("○ Camera 03 - Boundary Fence A")
        cam_3.setData(Qt.UserRole, "simulation")
        
        cam_4 = QListWidgetItem("○ Camera 04 - Tactical Sector B (Offline)")
        cam_4.setData(Qt.UserRole, "offline")
        cam_4.setFlags(cam_4.flags() & ~Qt.ItemIsEnabled) # Disabled
        
        self.camera_list.addItem(cam_1)
        self.camera_list.addItem(cam_2)
        self.camera_list.addItem(cam_3)
        self.camera_list.addItem(cam_4)
        
        self.camera_list.setCurrentRow(1) # Default to Camera 02 simulation
        self.camera_list.itemClicked.connect(self.change_camera_source)
        
        left_layout.addWidget(self.camera_list)
        
        # Add source buttons inside Left Sidebar Camera Manager
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(10, 10, 10, 10)
        btn_layout.setSpacing(8)
        
        self.btn_add_file = QPushButton("+ ADD VIDEO FILE")
        self.btn_add_file.setObjectName("addFileBtn")
        self.btn_add_file.setStyleSheet("""
            QPushButton {
                background-color: #1a1b28;
                color: #00d2ff;
                border: 1px dashed #00d2ff;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00d2ff;
                color: #0d0e15;
            }
        """)
        self.btn_add_file.clicked.connect(self.open_local_file)
        
        self.btn_add_stream = QPushButton("+ ADD RTSP/NETWORK STREAM")
        self.btn_add_stream.setObjectName("addStreamBtn")
        self.btn_add_stream.setStyleSheet("""
            QPushButton {
                background-color: #1a1b28;
                color: #ffea00;
                border: 1px dashed #ffea00;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #ffea00;
                color: #0d0e15;
            }
        """)
        self.btn_add_stream.clicked.connect(self.add_network_stream)
        
        btn_layout.addWidget(self.btn_add_file)
        btn_layout.addWidget(self.btn_add_stream)
        left_layout.addLayout(btn_layout)
        
        workspace_splitter.addWidget(left_panel)
        
        # 2B. CENTER CONTENT - SURVEILLANCE & CONTROLS
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(15, 15, 15, 15)
        center_layout.setSpacing(12)
        
        # Live Video Frame
        self.video_frame = QFrame()
        self.video_frame.setObjectName("videoContainer")
        self.video_frame_layout = QVBoxLayout(self.video_frame)
        self.video_frame_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_display_label = QLabel()
        self.video_display_label.setAlignment(Qt.AlignCenter)
        self.video_display_label.setScaledContents(True)
        self.video_display_label.setStyleSheet("background-color: #030406; border-radius: 5px;")
        self.video_frame_layout.addWidget(self.video_display_label)
        
        center_layout.addWidget(self.video_frame, stretch=4)
        
        # Toolbar Layout below Video
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        self.btn_normal = QPushButton("NORMAL")
        self.btn_normal.setCheckable(True)
        self.btn_normal.setChecked(True)
        self.btn_normal.setProperty("class", "controlBtn")
        self.btn_normal.clicked.connect(lambda: self.change_mode('normal'))
        
        self.btn_thermal = QPushButton("THERMAL")
        self.btn_thermal.setCheckable(True)
        self.btn_thermal.setProperty("class", "controlBtn")
        self.btn_thermal.clicked.connect(lambda: self.change_mode('thermal'))
        
        self.btn_night = QPushButton("NIGHT VISION")
        self.btn_night.setCheckable(True)
        self.btn_night.setProperty("class", "controlBtn")
        self.btn_night.clicked.connect(lambda: self.change_mode('night'))
        
        self.btn_fence = QPushButton("VIRTUAL FENCE")
        self.btn_fence.setCheckable(True)
        self.btn_fence.setChecked(True)
        self.btn_fence.setProperty("class", "controlBtn")
        self.btn_fence.clicked.connect(self.toggle_fence)
        
        self.btn_recording = QPushButton("RECORDING")
        self.btn_recording.setCheckable(True)
        self.btn_recording.setChecked(True)
        self.btn_recording.setProperty("class", "controlBtn")
        self.btn_recording.clicked.connect(self.toggle_recording)
        
        self.btn_open_file = QPushButton("OPEN VIDEO FILE")
        self.btn_open_file.setProperty("class", "controlBtn")
        self.btn_open_file.clicked.connect(self.open_local_file)
        
        self.engine_btn = QPushButton("LOCAL INFERENCE")
        self.engine_btn.setToolTip("Toggle local processing or uvicorn API request forwarding")
        self.engine_btn.setProperty("class", "controlBtn")
        self.engine_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1b28;
                color: #00d2ff;
                border: 1px solid #00d2ff;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.engine_btn.clicked.connect(self.toggle_inference_engine)

        toolbar_layout.addWidget(self.btn_normal)
        toolbar_layout.addWidget(self.btn_thermal)
        toolbar_layout.addWidget(self.btn_night)
        toolbar_layout.addSpacing(15)
        toolbar_layout.addWidget(self.btn_fence)
        toolbar_layout.addWidget(self.btn_recording)
        toolbar_layout.addWidget(self.engine_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.btn_open_file)
        
        center_layout.addLayout(toolbar_layout)
        workspace_splitter.addWidget(center_widget)
        
        # Set splitter properties (proportional scaling)
        workspace_splitter.setStretchFactor(0, 1)
        workspace_splitter.setStretchFactor(1, 4)
        
        main_layout.addWidget(workspace_splitter, stretch=4)
        
        # 3. BOTTOM PANEL - EVENT LOGGER
        bottom_panel = QWidget()
        bottom_panel.setObjectName("headerPanel") # Same dark container background
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(15, 10, 15, 15)
        bottom_layout.setSpacing(5)
        
        log_header_layout = QHBoxLayout()
        log_header_lbl = QLabel("LIVE SECURE SYS-LOG TERMINAL")
        log_header_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        log_header_lbl.setStyleSheet("color: #00d2ff; letter-spacing: 1px;")
        
        clear_btn = QPushButton("CLEAR LOGS")
        clear_btn.setStyleSheet("""
            background-color: transparent;
            color: #8f929d;
            border: 1px solid #2c2f46;
            padding: 3px 10px;
            font-size: 10px;
        """)
        clear_btn.clicked.connect(self.clear_logs)
        
        log_header_layout.addWidget(log_header_lbl)
        log_header_layout.addStretch()
        log_header_layout.addWidget(clear_btn)
        
        bottom_layout.addLayout(log_header_layout)
        
        # Table Grid log
        self.log_table = QTableWidget(0, 3)
        self.log_table.setObjectName("eventLogTable")
        self.log_table.setHorizontalHeaderLabels(["TIMESTAMP", "CLASSIFICATION", "EVENT DETECTED DETAILS"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.setColumnWidth(0, 120)
        self.log_table.setColumnWidth(1, 150)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setSelectionMode(QAbstractItemView.NoSelection)
        
        bottom_layout.addWidget(self.log_table, stretch=1)
        
        main_layout.addWidget(bottom_panel, stretch=1)
        
        # Central widget wrap
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def create_counter_card(self, title, initial_val, color_hex):
        frame = QFrame()
        frame.setObjectName("statWidget")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        
        val_lbl = QLabel(initial_val)
        val_lbl.setObjectName("statVal")
        val_lbl.setStyleSheet(f"color: {color_hex};")
        
        title_lbl = QLabel(title)
        title_lbl.setObjectName("statLabel")
        
        layout.addWidget(val_lbl, alignment=Qt.AlignHCenter)
        layout.addWidget(title_lbl, alignment=Qt.AlignHCenter)
        
        # Keep references inside card frame to retrieve value labels later
        frame.val_lbl = val_lbl
        return frame

    def update_clock(self):
        current_time = QTime.currentTime().toString("hh:mm:ss")
        current_date = time.strftime("%d-%b-%Y")
        self.clock_label.setText(f"{current_date} | {current_time} UTC+05:30")

    def change_camera_source(self, item):
        name = item.text()
        source = item.data(Qt.UserRole)
        
        if source == "offline":
            return
            
        self.add_log_entry(
            self.get_timestamp(),
            f"Network | Reconnecting server pipeline to source: {name}",
            "info"
        )
        self.video_thread.set_source(source)

    def open_local_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Border CCTV Video Feed", "", 
            "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)"
        )
        if file_path:
            self.add_log_entry(
                self.get_timestamp(),
                f"Source | Playing custom local file: {os.path.basename(file_path)}",
                "info"
            )
            self.video_thread.set_source(file_path)
            
            # Add entry to camera manager dynamically
            new_item = QListWidgetItem(f"● Custom: {os.path.basename(file_path)}")
            new_item.setData(Qt.UserRole, file_path)
            self.camera_list.addItem(new_item)
            self.camera_list.setCurrentItem(new_item)

    def change_mode(self, mode):
        # Reset buttons checked state
        self.btn_normal.setChecked(mode == 'normal')
        self.btn_thermal.setChecked(mode == 'thermal')
        self.btn_night.setChecked(mode == 'night')
        
        self.video_thread.set_display_mode(mode)
        self.add_log_entry(
            self.get_timestamp(),
            f"Display | Video processing shader changed to: {mode.upper()} mode.",
            "normal"
        )

    def toggle_fence(self):
        checked = self.btn_fence.isChecked()
        self.video_thread.set_fence_enabled(checked)
        status = "ACTIVE" if checked else "DISABLED"
        self.add_log_entry(
            self.get_timestamp(),
            f"Safety | Virtual Fence security perimeter is now: {status}.",
            "warning" if checked else "normal"
        )

    def toggle_recording(self):
        checked = self.btn_recording.isChecked()
        self.video_thread.set_recording_enabled(checked)
        status = "STARTED" if checked else "PAUSED"
        self.add_log_entry(
            self.get_timestamp(),
            f"System | Surveillance video file streaming recording: {status}.",
            "info"
        )

    def toggle_inference_engine(self):
        if self.video_thread.inference_engine == 'local':
            # Switch to API
            self.video_thread.set_inference_engine('api')
            self.engine_btn.setText("API INFERENCE")
            self.engine_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e3725;
                    color: #00ff66;
                    border: 1px solid #00ff66;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 11px;
                }
            """)
            self.add_log_entry(
                self.get_timestamp(),
                "Integration | Routing video stream frames to uvicorn FastAPI backend server.",
                "info"
            )
        else:
            # Switch to Local
            self.video_thread.set_inference_engine('local')
            self.engine_btn.setText("LOCAL INFERENCE")
            self.engine_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a1b28;
                    color: #00d2ff;
                    border: 1px solid #00d2ff;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 11px;
                }
            """)
            self.add_log_entry(
                self.get_timestamp(),
                "Integration | Processing YOLO algorithms locally on local CUDA/CPU cores.",
                "info"
            )

    def update_video_frame(self, q_image, detections, stats):
        # Draw frame into label
        pixmap = QPixmap.fromImage(q_image)
        # We rely on Qt's native setScaledContents(True) for dynamic responsive resizing
        self.video_display_label.setPixmap(pixmap)

    def handle_alert(self, alert_dict):
        pass

    def add_log_entry(self, timestamp, msg, level):
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        
        # Cells creation
        time_item = QTableWidgetItem(timestamp)
        time_item.setTextAlignment(Qt.AlignCenter)
        
        # Color coding cell text based on level
        lvl_item = QTableWidgetItem()
        lvl_item.setTextAlignment(Qt.AlignCenter)
        
        msg_item = QTableWidgetItem(msg)
        
        if level == "critical":
            lvl_item.setText("🚨 CRITICAL")
            lvl_item.setForeground(Qt.red)
            time_item.setForeground(Qt.red)
            msg_item.setForeground(Qt.red)
        elif level == "warning":
            lvl_item.setText("⚠️ WARNING")
            lvl_item.setForeground(Qt.yellow)
            time_item.setForeground(Qt.yellow)
            msg_item.setForeground(Qt.yellow)
        elif level == "info":
            lvl_item.setText("ℹ️ INFO")
            lvl_item.setForeground(Qt.cyan)
        else:
            lvl_item.setText("✓ NORMAL")
            lvl_item.setForeground(Qt.green)
            
        self.log_table.setItem(row, 0, time_item)
        self.log_table.setItem(row, 1, lvl_item)
        self.log_table.setItem(row, 2, msg_item)
        
        # Auto scroll to bottom
        self.log_table.scrollToBottom()

    def clear_logs(self):
        self.log_table.setRowCount(0)

    def get_timestamp(self):
        return time.strftime("%H:%M:%S")

    def add_network_stream(self):
        url, ok = QInputDialog.getText(
            self, "Add Security Camera Stream", 
            "Enter RTSP/HTTP video stream URL:\n(e.g., rtsp://username:password@ip:port/h264 or http://ip:port/stream)"
        )
        if ok and url:
            name = f"● Stream: {url.split('@')[-1] if '@' in url else url[:30]}"
            self.add_log_entry(
                self.get_timestamp(),
                f"Source | Adding network stream source: {url}",
                "info"
            )
            
            # Add to list widget
            new_item = QListWidgetItem(name)
            new_item.setData(Qt.UserRole, url)
            self.camera_list.addItem(new_item)
            self.camera_list.setCurrentItem(new_item)
            
            # Switch source immediately
            self.video_thread.set_source(url)

    def closeEvent(self, event):
        # Stop background thread on window exit
        self.video_thread.stop()
        event.accept()


if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
