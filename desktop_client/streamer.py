import cv2
import asyncio
import websockets
import numpy as np
import pyvirtualcam
from pyvirtualcam import PixelFormat
import threading
from PySide6.QtCore import QObject, Signal

class VisoStreamer(QObject):
    frame_ready = Signal(np.ndarray)
    error_occurred = Signal(str)

    def __init__(self, websocket_url: str, camera_index: int = 0, use_virtual_cam: bool = False):
        super().__init__()
        self.websocket_url = websocket_url
        self.camera_index = camera_index
        self.use_virtual_cam = use_virtual_cam
        self.running = False
        self.loop = None
        self._thread = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._stream_task())
        except Exception as e:
            print(f"Stream error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.loop.close()

    async def _stream_task(self):
        print(f"[DEBUG] Opening camera {self.camera_index}...")
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("[DEBUG] CAP_DSHOW failed, trying default...")
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error_occurred.emit("Failed to open camera.")
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or fps is None or np.isnan(fps):
            fps = 30.0
        print(f"[DEBUG] Camera: {width}x{height} @ {fps}fps")

        cam = None
        if self.use_virtual_cam:
            try:
                cam = pyvirtualcam.Camera(width=width, height=height, fps=fps, fmt=PixelFormat.RGB)
                print(f"[DEBUG] Virtual camera: {cam.device}")
            except Exception as e:
                print(f"[DEBUG] Virtual camera warning: {e}")
                self.error_occurred.emit(f"Virtual camera warning: {e}\nLive Preview will still work!")

        try:
            print(f"[DEBUG] Connecting to {self.websocket_url}...")
            async with websockets.connect(self.websocket_url) as ws:
                print("[DEBUG] WebSocket connected.")
                while self.running:
                    ret, frame = cap.read()
                    if not ret:
                        await asyncio.sleep(0.01)
                        continue

                    # -- OPTIMIZATION: Downscale for transmission --
                    # This dramatically reduces network latency.
                    h, w = frame.shape[:2]
                    max_h = 480
                    if h > max_h:
                        scale = max_h / h
                        frame_small = cv2.resize(frame, (int(w * scale), max_h))
                    else:
                        frame_small = frame

                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                    r, encoded_img = cv2.imencode('.jpg', frame_small, encode_param)
                    if not r:
                        continue

                    await ws.send(encoded_img.tobytes())

                    try:
                        # Wait for processed frame
                        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        nparr = np.frombuffer(response, np.uint8)
                        processed_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                        if processed_frame is not None:
                            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                            self.frame_ready.emit(rgb_frame)

                            if cam:
                                # Re-scale to original camera size for Virtual Camera output
                                if rgb_frame.shape[1] != width or rgb_frame.shape[0] != height:
                                    vcam_frame = cv2.resize(rgb_frame, (width, height))
                                else:
                                    vcam_frame = rgb_frame
                                cam.send(vcam_frame)
                                cam.sleep_until_next_frame()
                    except asyncio.TimeoutError:
                        print("[DEBUG] Response timeout.")
                    except Exception as e:
                        print(f"[DEBUG] Receive error: {e}")
                        break

        except Exception as e:
            print(f"Error in stream: {e}")
            self.error_occurred.emit(str(e))
        finally:
            if cam:
                cam.close()
            cap.release()
            print("Capture released.")
