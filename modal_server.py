# modal_server.py

import modal
import cv2
import numpy as np

app = modal.App("visomaster-headless")

image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04", add_python="3.10")
    .apt_install("ffmpeg", "libgl1", "libglib2.0-0", "git", "build-essential", "clang")
    .pip_install(
        "fastapi", "uvicorn", "websockets", "python-multipart", "insightface"
    )
    .run_commands(
        # Clone YOUR fork (with the headless refactor)
        "git clone https://github.com/Elavn/VisoMaster /app/VisoMaster",
        "cd /app/VisoMaster && pip install -r requirements_cu124.txt --quiet"
    )
    .add_local_file("headless_config.py", remote_path="/app/VisoMaster/headless_config.py")
    .add_local_file("headless_engine.py", remote_path="/app/VisoMaster/headless_engine.py")
    .add_local_file("app/processors/models_processor.py", remote_path="/app/VisoMaster/app/processors/models_processor.py")
    .add_local_file("app/processors/face_detectors.py", remote_path="/app/VisoMaster/app/processors/face_detectors.py")
)

volume = modal.Volume.from_name("visomaster-models", create_if_missing=True)

@app.cls(
    image=image,
    gpu="A10G",
    volumes={"/models": volume},
    scaledown_window=300,
)
class VisoServer:

    @modal.enter()
    def startup(self):
        import sys
        import os
        sys.path.insert(0, '/app/VisoMaster')
        from headless_engine import HeadlessEngine
        self.engine = HeadlessEngine(model_dir='/models')
        
        face_path = '/models/source_face.jpg'
        if os.path.exists(face_path):
            self.engine.set_source_face(face_path)
            print("🚀 VisoMaster headless ready. Source face loaded!")
        else:
            print(f"⚠️ WARNING: {face_path} not found on the volume. Face swapping will just return the original frame.")
            print("To fix this, upload an image from your terminal using:")
            print("  modal volume put visomaster-models path/to/local/face.jpg source_face.jpg")

    @modal.asgi_app()
    def serve(self):
        from fastapi import FastAPI, WebSocket, UploadFile, File
        api = FastAPI()

        @api.post("/set_source")
        async def set_source(file: UploadFile = File(...)):
            content = await file.read()
            face_path = '/models/source_face.jpg'
            with open(face_path, 'wb') as f:
                f.write(content)
            
            try:
                self.engine.set_source_face(face_path)
                return {"status": "success", "message": "Source face updated"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @api.post("/update_settings")
        async def update_settings(request: dict):
            try:
                self.engine.update_settings(request)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @api.websocket("/swap")
        async def swap_ws(ws: WebSocket):
            await ws.accept()
            while True:
                try:
                    data = await ws.receive_bytes()
                    frame = cv2.imdecode(
                        np.frombuffer(data, np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    result = self.engine.process_frame(frame)
                    _, buf = cv2.imencode(
                        '.jpg', result,
                        [cv2.IMWRITE_JPEG_QUALITY, 65]
                    )
                    await ws.send_bytes(buf.tobytes())
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"WS Error: {e}")
                    break

        return api
