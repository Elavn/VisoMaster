import sys
import threading
import requests
import os
import json
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
                               QMessageBox, QSizePolicy, QFileDialog, QProgressBar,
                               QCheckBox, QSlider, QDoubleSpinBox, QGroupBox, QSpinBox,
                               QScrollArea)
from PySide6.QtCore import Qt, QTimer, Slot, Signal
from PySide6.QtGui import QImage, QPixmap
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from streamer import VisoStreamer

class VisoMasterClient(QMainWindow):
    upload_progress_signal = Signal(int)

    def __init__(self):
        super().__init__()
        self.upload_progress_signal.connect(self.update_upload_progress)
        self.setWindowTitle("VisoMaster Desktop Client")
        self.setMinimumSize(1200, 800)
        self._settings_timer = QTimer()
        self._settings_timer.setSingleShot(True)
        self._settings_timer.setInterval(300)
        self._settings_timer.timeout.connect(self._send_settings)

        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QLabel { color: #e0e0e0; font-family: 'Segoe UI', Arial; font-size: 10pt; }
            QLabel#previewLabel { background-color: #000; border: 2px solid #3d3d3d; border-radius: 8px; }
            QLineEdit, QComboBox { padding: 6px; background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px; color: #fff; font-size: 10pt; }
            QPushButton { background-color: #007acc; color: white; border: none; padding: 10px 16px; border-radius: 4px; font-weight: bold; font-size: 10pt; }
            QPushButton:hover { background-color: #0098ff; }
            QPushButton#stopBtn { background-color: #cc3333; }
            QPushButton#stopBtn:hover { background-color: #ff4444; }
            QGroupBox { color: #e0e0e0; border: 1px solid #3d3d3d; border-radius: 6px; margin-top: 8px; padding-top: 16px; font-weight: bold; font-size: 10pt; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QCheckBox { color: #e0e0e0; font-size: 10pt; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QSlider::groove:horizontal { border: 1px solid #3d3d3d; height: 6px; background: #2d2d2d; border-radius: 3px; }
            QSlider::handle:horizontal { background: #007acc; width: 14px; margin: -5px 0; border-radius: 7px; }
            QSpinBox, QDoubleSpinBox { background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px; color: #fff; padding: 4px; font-size: 10pt; }
            QScrollArea { border: none; background-color: transparent; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        
        # Main Horizontal Layout
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(16, 16, 16, 16)
        h_layout.setSpacing(20)

        # --- LEFT COLUMN: Preview & Info ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("VisoMaster Headless Client")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #fff; margin-bottom: 5px;")
        left_layout.addWidget(title)

        self.preview_label = QLabel("Camera Preview\n(Offline)")
        self.preview_label.setObjectName("previewLabel")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(640, 480)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.preview_label)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color: #aaa; font-style: italic; font-size: 11pt; border-top: 1px solid #333; padding-top: 10px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.status_label)
        
        h_layout.addWidget(left_widget, 1)

        # --- RIGHT COLUMN: Controls ---
        right_widget = QWidget()
        right_widget.setFixedWidth(400)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        controls_layout = QVBoxLayout(scroll_widget)
        controls_layout.setSpacing(10)
        controls_layout.setContentsMargins(0, 0, 10, 0)

        # Connection
        conn_group = QGroupBox("Connection")
        conn_lay = QVBoxLayout(conn_group)
        conn_lay.addWidget(QLabel("Modal WS URL:"))
        self.ws_input = QLineEdit("wss://YOUR_MODAL_URL/swap")
        conn_lay.addWidget(self.ws_input)
        
        cam_h_lay = QHBoxLayout()
        cam_h_lay.addWidget(QLabel("Camera:"))
        self.cam_combo = QComboBox()
        self.cam_combo.addItem("Default Camera (0)", 0)
        for i in range(1, 10):
            self.cam_combo.addItem(f"Camera {i}", i)
        cam_h_lay.addWidget(self.cam_combo, 1)
        conn_lay.addLayout(cam_h_lay)
        controls_layout.addWidget(conn_group)

        # Source Face
        src_group = QGroupBox("Source Face")
        src_lay = QVBoxLayout(src_group)
        self.source_path_input = QLineEdit("No image selected")
        self.source_path_input.setReadOnly(True)
        src_lay.addWidget(self.source_path_input)
        
        src_btn_lay = QHBoxLayout()
        self.source_browse_btn = QPushButton("Browse")
        self.source_browse_btn.clicked.connect(self.browse_source_image)
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self.upload_source_image)
        self.upload_btn.setEnabled(False)
        src_btn_lay.addWidget(self.source_browse_btn)
        src_btn_lay.addWidget(self.upload_btn)
        src_lay.addLayout(src_btn_lay)
        
        self.upload_progress = QProgressBar()
        self.upload_progress.setRange(0, 100)
        self.upload_progress.setVisible(False)
        self.upload_progress.setFixedHeight(8)
        src_lay.addWidget(self.upload_progress)
        controls_layout.addWidget(src_group)

        # Swapper Settings
        swap_group = QGroupBox("Swapper Settings")
        swap_lay = QVBoxLayout(swap_group)
        
        res_lay = QHBoxLayout()
        res_lay.addWidget(QLabel("Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(['128', '256', '384', '512'])
        self.res_combo.setCurrentText('128')
        self.res_combo.currentTextChanged.connect(self._schedule_settings)
        res_lay.addWidget(self.res_combo, 1)
        swap_lay.addLayout(res_lay)

        sim_lay = QHBoxLayout()
        sim_lay.addWidget(QLabel("Similarity:"))
        self.sim_spin = QSpinBox()
        self.sim_spin.setRange(0, 100)
        self.sim_spin.setValue(60)
        self.sim_spin.valueChanged.connect(self._schedule_settings)
        sim_lay.addWidget(self.sim_spin, 1)
        swap_lay.addLayout(sim_lay)
        
        controls_layout.addWidget(swap_group)

        # Face Likeness
        like_group = QGroupBox("Face Likeness")
        like_lay = QVBoxLayout(like_group)
        self.likeness_check = QCheckBox("Enable Face Likeness")
        self.likeness_check.toggled.connect(self._schedule_settings)
        like_lay.addWidget(self.likeness_check)
        
        like_val_lay = QHBoxLayout()
        like_val_lay.addWidget(QLabel("Amount:"))
        self.likeness_spin = QDoubleSpinBox()
        self.likeness_spin.setRange(-1.0, 1.0)
        self.likeness_spin.setSingleStep(0.05)
        self.likeness_spin.setValue(0.0)
        self.likeness_spin.valueChanged.connect(self._schedule_settings)
        like_val_lay.addWidget(self.likeness_spin, 1)
        like_lay.addLayout(like_val_lay)
        controls_layout.addWidget(like_group)

        # Face Restorer
        rest_group = QGroupBox("Face Restorer")
        rest_lay = QVBoxLayout(rest_group)
        self.restorer_check = QCheckBox("Enable Restorer")
        self.restorer_check.toggled.connect(self._schedule_settings)
        rest_lay.addWidget(self.restorer_check)

        type_lay = QHBoxLayout()
        type_lay.addWidget(QLabel("Type:"))
        self.restorer_type = QComboBox()
        self.restorer_type.addItems(['GFPGAN-v1.4', 'CodeFormer', 'RestoreFormer++', 'VQFR-v2'])
        self.restorer_type.currentTextChanged.connect(self._schedule_settings)
        type_lay.addWidget(self.restorer_type, 1)
        rest_lay.addLayout(type_lay)

        rest_fid_lay = QHBoxLayout()
        rest_fid_lay.addWidget(QLabel("Fidelity:"))
        self.restorer_fidelity = QDoubleSpinBox()
        self.restorer_fidelity.setRange(0.0, 1.0)
        self.restorer_fidelity.setSingleStep(0.1)
        self.restorer_fidelity.setValue(0.9)
        self.restorer_fidelity.valueChanged.connect(self._schedule_settings)
        rest_fid_lay.addWidget(self.restorer_fidelity, 1)
        rest_lay.addLayout(rest_fid_lay)

        blend_lay = QHBoxLayout()
        blend_lay.addWidget(QLabel("Blend:"))
        self.restorer_blend = QSpinBox()
        self.restorer_blend.setRange(0, 100)
        self.restorer_blend.setValue(100)
        self.restorer_blend.valueChanged.connect(self._schedule_settings)
        blend_lay.addWidget(self.restorer_blend, 1)
        rest_lay.addLayout(blend_lay)
        controls_layout.addWidget(rest_group)

        # Occlusion Mask
        occ_group = QGroupBox("Occlusion Mask")
        occ_lay = QVBoxLayout(occ_group)
        self.occ_check = QCheckBox("Enable Occlusion")
        self.occ_check.toggled.connect(self._schedule_settings)
        occ_lay.addWidget(self.occ_check)
        
        occ_size_lay = QHBoxLayout()
        occ_size_lay.addWidget(QLabel("Size:"))
        self.occ_size_spin = QSpinBox()
        self.occ_size_spin.setRange(-100, 100)
        self.occ_size_spin.setValue(0)
        self.occ_size_spin.valueChanged.connect(self._schedule_settings)
        occ_size_lay.addWidget(self.occ_size_spin, 1)
        occ_lay.addLayout(occ_size_lay)
        controls_layout.addWidget(occ_group)

        # Mask Borders (Added to help with the "blur square line")
        mask_group = QGroupBox("Mask Management")
        mask_lay = QVBoxLayout(mask_group)
        
        # Border settings
        for side in ['Top', 'Bottom', 'Left', 'Right']:
            lay = QHBoxLayout()
            lay.addWidget(QLabel(f"Border {side}:"))
            sb = QSpinBox()
            sb.setRange(0, 64)
            sb.setValue(10)
            sb.valueChanged.connect(self._schedule_settings)
            setattr(self, f"mask_border_{side.lower()}", sb)
            lay.addWidget(sb, 1)
            mask_lay.addLayout(lay)
            
        lay_blur = QHBoxLayout()
        lay_blur.addWidget(QLabel("Overall Blur:"))
        self.mask_blur = QSpinBox()
        self.mask_blur.setRange(0, 50)
        self.mask_blur.setValue(10)
        self.mask_blur.valueChanged.connect(self._schedule_settings)
        lay_blur.addWidget(self.mask_blur, 1)
        mask_lay.addLayout(lay_blur)
        
        controls_layout.addWidget(mask_group)

        # Virtual Camera
        vcam_group = QGroupBox("Output")
        vcam_lay = QVBoxLayout(vcam_group)
        self.vcam_check = QCheckBox("Virtual Camera Output")
        vcam_lay.addWidget(self.vcam_check)
        controls_layout.addWidget(vcam_group)

        scroll.setWidget(scroll_widget)
        right_layout.addWidget(scroll)

        # Buttons at bottom of right column
        btn_lay = QHBoxLayout()
        self.start_btn = QPushButton("START STREAM")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.clicked.connect(self.start_stream)
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.clicked.connect(self.stop_stream)
        self.stop_btn.setEnabled(False)
        btn_lay.addWidget(self.start_btn, 2)
        btn_lay.addWidget(self.stop_btn, 1)
        right_layout.addLayout(btn_lay)

        h_layout.addWidget(right_widget)

        self.streamer = None

    # ---- Settings sync ----
    def _schedule_settings(self):
        self._settings_timer.start()

    def _get_base_url(self):
        ws_url = self.ws_input.text().strip()
        url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
        if url.endswith("/swap"):
            url = url[:-5]
        return url

    def _send_settings(self):
        settings = {
            'SwapperResSelection': self.res_combo.currentText(),
            'SimilarityThresholdSlider': self.sim_spin.value(),
            'FaceLikenessEnableToggle': self.likeness_check.isChecked(),
            'FaceLikenessFactorDecimalSlider': self.likeness_spin.value(),
            'OccluderEnableToggle': self.occ_check.isChecked(),
            'OccluderSizeSlider': self.occ_size_spin.value(),
            'FaceRestorerEnableToggle': self.restorer_check.isChecked(),
            'FaceRestorerTypeSelection': self.restorer_type.currentText(),
            'FaceRestorerDetTypeSelection': 'Original', # Simplified alignment for UI
            'FaceFidelityWeightDecimalSlider': self.restorer_fidelity.value(),
            'FaceRestorerBlendSlider': self.restorer_blend.value(),
            # Border masks
            'BorderTopSlider': self.mask_border_top.value(),
            'BorderBottomSlider': self.mask_border_bottom.value(),
            'BorderLeftSlider': self.mask_border_left.value(),
            'BorderRightSlider': self.mask_border_right.value(),
            'OverallMaskBlendAmountSlider': self.mask_blur.value(),
        }
        url = self._get_base_url() + "/update_settings"
        threading.Thread(target=self._post_settings, args=(url, settings), daemon=True).start()

    def _post_settings(self, url, settings):
        try:
            r = requests.post(url, json=settings, timeout=10)
            if r.status_code == 200:
                print(f"[Settings] Synced: {list(settings.keys())}")
            else:
                print(f"[Settings] Error: {r.status_code}")
        except Exception as e:
            print(f"[Settings] Connection error: {e}")

    # ---- Source face ----
    def browse_source_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_name:
            self.source_path_input.setText(file_name)
            self.upload_btn.setEnabled(True)

    def upload_source_image(self):
        http_url = self._get_base_url() + "/set_source"
        filepath = self.source_path_input.text()
        if not os.path.exists(filepath):
            QMessageBox.warning(self, "Error", "Selected file does not exist.")
            return

        self.status_label.setText("Status: Uploading...")
        self.upload_btn.setEnabled(False)
        self.source_browse_btn.setEnabled(False)
        self.upload_progress.setValue(0)
        self.upload_progress.setVisible(True)
        threading.Thread(target=self._upload_thread, args=(http_url, filepath), daemon=True).start()

    def _upload_thread(self, url, filepath):
        try:
            def create_callback(encoder):
                def callback(monitor):
                    pct = int(monitor.bytes_read / monitor.len * 100)
                    self.upload_progress_signal.emit(pct)
                return callback

            with open(filepath, 'rb') as f:
                encoder = MultipartEncoder(fields={'file': (os.path.basename(filepath), f, 'image/jpeg')})
                monitor = MultipartEncoderMonitor(encoder, create_callback(encoder))
                headers = {'Content-Type': monitor.content_type}
                response = requests.post(url, data=monitor, headers=headers, timeout=60)

            if response.status_code == 200:
                QTimer.singleShot(0, lambda: self.upload_success())
            else:
                QTimer.singleShot(0, lambda err=str(response.status_code): self.upload_error(f"HTTP {err}"))
        except Exception as e:
            QTimer.singleShot(0, lambda err=str(e): self.upload_error(err))

    @Slot(int)
    def update_upload_progress(self, pct):
        self.upload_progress.setValue(pct)
        if pct == 100:
            self.status_label.setText("Status: Server Processing...")

    def upload_success(self):
        self.status_label.setText("Status: Source Face Verified!")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.upload_progress.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.source_browse_btn.setEnabled(True)

    def upload_error(self, err_msg):
        self.status_label.setText(f"Status: Error - {err_msg}")
        self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.upload_progress.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.source_browse_btn.setEnabled(True)

    # ---- Streaming ----
    def start_stream(self):
        url = self.ws_input.text().strip()
        if not url.startswith("ws"):
            QMessageBox.warning(self, "Error", "Invalid WebSocket URL.")
            return

        cam_idx = self.cam_combo.currentData()
        use_vcam = self.vcam_check.isChecked()

        self.streamer = VisoStreamer(websocket_url=url, camera_index=cam_idx, use_virtual_cam=use_vcam)
        self.streamer.frame_ready.connect(self.update_preview)
        self.streamer.error_occurred.connect(self.handle_error)
        self.streamer.start()

        self._send_settings()

        self.status_label.setText("Status: LIVE")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11pt;")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_stream(self):
        if self.streamer:
            self.streamer.stop()
            self.streamer = None
        self.status_label.setText("Status: Idle")
        self.status_label.setStyleSheet("color: #aaa; font-style: italic;")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.preview_label.setText("Camera Preview\n(Offline)")

    @Slot(np.ndarray)
    def update_preview(self, rgb_frame: np.ndarray):
        h, w, ch = rgb_frame.shape
        qimg = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
        scaled = QPixmap.fromImage(qimg).scaled(
            self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)

    @Slot(str)
    def handle_error(self, message: str):
        QMessageBox.critical(self, "Error", message)
        self.stop_stream()

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VisoMasterClient()
    window.show()
    sys.exit(app.exec())
