import sys
import cv2
import numpy as np
import torch
from unittest.mock import MagicMock

sys.path.insert(0, '/app/VisoMaster')

# --- Mock all Qt/UI modules that frame_worker.py imports at the top level ---
# We must mock parent packages too so that 'import app.ui.xxx' works correctly.
mock = MagicMock()
for mod_name in [
    'pyqttoast',
    'qtpy', 'qtpy.QtGui', 'qtpy.QtCore', 'qtpy.QtWidgets',
    'app.ui',
    'app.ui.widgets',
    'app.ui.widgets.actions',
    'app.ui.widgets.actions.common_actions',
    'app.ui.widgets.actions.video_control_actions',
    'app.ui.main_ui',
]:
    sys.modules[mod_name] = mock

# Ensure 'app' has a 'ui' attribute
import app
if not hasattr(app, 'ui'):
    app.ui = mock

from headless_config import DEFAULT_CONTROLS, DEFAULT_PARAMETERS
from app.processors.models_processor import ModelsProcessor
from app.helpers.miscellaneous import ParametersDict
from app.processors.workers.frame_worker import FrameWorker


class HeadlessEngine:
    def __init__(self, model_dir: str = '/models', controls_override: dict = None):
        controls = {**DEFAULT_CONTROLS, 'ModelsDir': model_dir}
        if controls_override:
            controls.update(controls_override)

        self.processor = ModelsProcessor(
            controls=controls,
            parameters=DEFAULT_PARAMETERS,
            device='cuda'
        )
        self.source_swap_embedding = None
        self.parameters = dict(DEFAULT_PARAMETERS)
        self.controls = controls

        # Create a FrameWorker instance without calling __init__ (we only need its methods)
        self._worker = FrameWorker.__new__(FrameWorker)
        self._worker.models_processor = self.processor
        self._worker.is_view_face_compare = False
        self._worker.is_view_face_mask = False
        self._worker.parameters = self.parameters

    def update_settings(self, settings: dict):
        """Merge new settings from the client into runtime parameters."""
        self.parameters.update(settings)
        print(f"⚙️  Settings updated: {list(settings.keys())}")

    def set_source_face(self, image_path: str) -> bool:
        """Load and embed the source face."""
        cv_img = cv2.imread(image_path)
        if cv_img is None:
            raise FileNotFoundError(f"Source face image not found: {image_path}")

        img = torch.from_numpy(cv_img.astype('uint8')).to(self.processor.device)
        img = img.permute(2, 0, 1)

        bboxes, kpss5, _ = self.processor.run_detect(
            img,
            self.controls['DetectorModelSelection'],
            max_num=1,
            score=self.controls['DetectorScoreSlider'] / 100.0,
            input_size=(512, 512),
            use_landmark_detection=True,
            landmark_detect_mode=self.controls['LandmarkDetectModelSelection'],
            landmark_score=0.5,
            from_points=False,
            rotation_angles=[0]
        )

        if len(bboxes) == 0:
            raise ValueError("No face detected in source image")

        # Compute the source embedding using the arcface model the swapper expects
        arcface_model = self.processor.get_arcface_model(self.controls['SwapperModelSelection'])
        self.source_swap_embedding, _ = self.processor.run_recognize_direct(
            img, kpss5[0],
            self.controls['SimilarityTypeSelection'],
            arcface_model
        )

        # Pre-load the swapper model
        swapper_model = self.controls['SwapperModelSelection']
        self.processor.load_inswapper_iss_emap(swapper_model)
        self.processor.models[swapper_model] = self.processor.load_model(swapper_model)

        print(f"✅ Source face embedded — vector shape: {self.source_swap_embedding.shape}")
        return True

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Run face swap using the ORIGINAL VisoMaster swap_core pipeline."""
        if self.source_swap_embedding is None:
            return frame

        img = torch.from_numpy(frame.astype('uint8')).to(self.processor.device)
        img = img.permute(2, 0, 1)

        # Detect faces in the frame
        bboxes, kpss5, kpss = self.processor.run_detect(
            img,
            self.controls['DetectorModelSelection'],
            max_num=1,
            score=self.controls['DetectorScoreSlider'] / 100.0,
            input_size=(512, 512),
            use_landmark_detection=self.controls.get('LandmarkDetectToggle', True),
            landmark_detect_mode=self.controls.get('LandmarkDetectModelSelection', '2dfan4'),
            landmark_score=0.5,
            from_points=False,
            rotation_angles=[0]
        )

        if len(bboxes) == 0:
            return frame

        # Get the target embedding from the detected face in the video frame
        kps_5 = kpss5[0]
        arcface_model = self.processor.get_arcface_model(self.controls['SwapperModelSelection'])
        target_embedding, _ = self.processor.run_recognize_direct(
            img, kps_5,
            self.controls['SimilarityTypeSelection'],
            arcface_model
        )

        # Build parameters dict matching original VisoMaster format
        params = ParametersDict(self.parameters, DEFAULT_PARAMETERS)

        # Call the ORIGINAL VisoMaster swap_core — 1:1 quality parity!
        img, _, _ = self._worker.swap_core(
            img,
            kps_5,
            s_e=self.source_swap_embedding,
            t_e=target_embedding,
            parameters=params,
            control=self.controls,
        )

        return img.permute(1, 2, 0).cpu().numpy().astype('uint8')
