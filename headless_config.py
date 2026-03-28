# headless_config.py
# Drop this file into your VisoMaster fork root

DEFAULT_CONTROLS = {
    # --- Execution ---
    'ProvidersPrioritySelection': 'CUDA',
    'ThreadsNumberSlider': 4,

    # --- Detection ---
    'DetectorModelSelection': 'RetinaFace',
    'DetectorScoreSlider': 65,
    'AutoRotationToggle': False,
    'DetectFromPointsToggle': False,
    'MaxFacesToDetectSlider': 1,

    # --- Landmarks ---
    'LandmarkDetectToggle': True,
    'LandmarkDetectModelSelection': '2dfan4',
    'LandmarkDetectScoreSlider': 50,

    # --- Recognition ---
    'RecognitionModelSelection': 'CSCSArcFace',
    'SimilarityTypeSelection': 'Opal',

    # --- Swapping ---
    'SwapperModelSelection': 'Inswapper128',
    'SwapperTypeSelection': 'swap',

    # --- Enhancement ---
    'RestorerModelSelection': 'GFPGAN',
    'RestorerToggle': False,
    'RestorerTypeSelection': 'full',
    'FrameEnhancerEnableToggle': False,

    # --- Masking ---
    'MaskTypeSelection': 'box',
    'MaskBlurSlider': 20,
    'MaskErodesSlider': 5,

    # --- Misc UI toggles (headless defaults) ---
    'ManualRotationEnableToggle': False,
    'ManualRotationAngleSlider': 0,
    'ShowAllDetectedFacesBBoxToggle': False,
    'ShowLandmarksEnableToggle': False,

    # --- Paths ---
    'ModelsDir': '/models',
}

# Per-face parameters — ALL keys that swap_core accesses must be here
DEFAULT_PARAMETERS = {
    # --- Swap Model ---
    'SwapModelSelection': 'Inswapper128',
    'SwapperResSelection': '128',
    'DFMModelSelection': '',

    # --- Face Adjustments ---
    'FaceAdjEnableToggle': False,
    'KpsXSlider': 0,
    'KpsYSlider': 0,
    'KpsScaleSlider': 0,
    'FaceScaleAmountSlider': 0,

    # --- Similarity ---
    'SimilarityThresholdSlider': 60,

    # --- Strength ---
    'StrengthEnableToggle': False,
    'StrengthAmountSlider': 100,

    # --- Face Likeness ---
    'FaceLikenessEnableToggle': False,
    'FaceLikenessFactorDecimalSlider': 0.0,

    # --- Face Restorer ---
    'FaceRestorerEnableToggle': False,
    'FaceRestorerTypeSelection': 'GFPGAN-v1.4',
    'FaceRestorerDetTypeSelection': 'Original',
    'FaceFidelityWeightDecimalSlider': 0.9,
    'FaceRestorerBlendSlider': 100,
    'FaceRestorerEnable2Toggle': False,
    'FaceRestorerType2Selection': 'GFPGAN-v1.4',
    'FaceRestorerDetType2Selection': 'Original',
    'FaceFidelityWeight2DecimalSlider': 0.9,
    'FaceRestorerBlend2Slider': 100,

    # --- Expression Restorer ---
    'FaceExpressionEnableToggle': False,

    # --- Occlusion Mask ---
    'OccluderEnableToggle': False,
    'OccluderSizeSlider': 0,
    'OccluderXSegBlurSlider': 0,
    'DFLXSegEnableToggle': False,
    'DFLXSegSizeSlider': 0,
    'FaceParserEnableToggle': False,
    'ClipEnableToggle': False,

    # --- Border Mask ---
    'BorderTopSlider': 10,
    'BorderBottomSlider': 10,
    'BorderLeftSlider': 10,
    'BorderRightSlider': 10,
    'BorderBlurSlider': 10,
    'OverallMaskBlendAmountSlider': 10,

    # --- Restore Eyes/Mouth ---
    'RestoreEyesEnableToggle': False,
    'RestoreMouthEnableToggle': False,
    'RestoreEyesMouthBlurSlider': 5,

    # --- Differencing ---
    'DifferencingEnableToggle': False,
    'DifferencingAmountSlider': 4,
    'DifferencingBlendAmountSlider': 5,

    # --- Auto Color ---
    'AutoColorEnableToggle': False,
    'AutoColorTransferTypeSelection': 'Test',
    'AutoColorBlendAmountSlider': 50,

    # --- Color Corrections ---
    'ColorEnableToggle': False,
    'ColorGammaDecimalSlider': 1.0,
    'ColorRedSlider': 0,
    'ColorGreenSlider': 0,
    'ColorBlueSlider': 0,
    'ColorBrightnessDecimalSlider': 1.0,
    'ColorContrastDecimalSlider': 1.0,
    'ColorSaturationDecimalSlider': 1.0,
    'ColorSharpnessDecimalSlider': 1.0,
    'ColorHueDecimalSlider': 0.0,
    'ColorNoiseDecimalSlider': 0.0,

    # --- JPEG Compression ---
    'JPEGCompressionEnableToggle': False,
    'JPEGCompressionAmountSlider': 85,

    # --- Final Blend ---
    'FinalBlendAdjEnableToggle': False,
    'FinalBlendAmountSlider': 0,

    # --- Keypoints Position (for landmark adjustments) ---
    'LandmarksPositionAdjEnableToggle': False,

    # --- Misc ---
    'FaceSwapperToggle': True,
    'FaceEditorToggle': False,
}
