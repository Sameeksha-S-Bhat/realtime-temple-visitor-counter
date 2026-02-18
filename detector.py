import cv2
import numpy as np
from ultralytics import YOLO
import config
import logging
import torch

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)


class PersonDetector:
    """
    AI-based person detection using YOLOv8
    Optimized for detecting people at normal walking speed
    GPU-accelerated
    """

    def __init__(self):
        try:
            logger.info("Loading YOLOv8 model...")

            # Check for GPU availability
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f"Using device: {self.device}")

            if self.device == 'cpu':
                logger.warning("Running on CPU - performance will be slower!")
                logger.warning(
                    "For better performance, install CUDA and PyTorch GPU version")

            # Using YOLOv8n (nano) - fastest model
            self.model = YOLO('yolov8n.pt')
            self.model.to(self.device)

            # OPTIMIZATION: Set model to FP16 for GPU (2x faster)
            if self.device == 'cuda':
                self.model.half()
                logger.info("Enabled FP16 mode for GPU acceleration")

            logger.info("Model loaded successfully!")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

        self.conf_threshold = config.CONFIDENCE_THRESHOLD
        self.min_height = config.MIN_PERSON_HEIGHT
        self.max_height = config.MAX_PERSON_HEIGHT

        # OPTIMIZATION: Warm up the model
        logger.info("Warming up model...")
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        _ = self.detect(dummy)
        logger.info("Model ready!")

    def detect(self, frame):
        """
        Detect persons in frame
        Optimized for normal walking speed and multiple people
        Returns: List of bounding boxes [(x1, y1, x2, y2, confidence), ...]
        """
        if frame is None:
            return []

        try:
            # Run detection with settings optimized for normal speed movement
            results = self.model(
                frame,
                conf=self.conf_threshold,  # Lower threshold catches more
                verbose=False,
                device=self.device,
                half=True if self.device == 'cuda' else False,
                imgsz=640,  # Standard size for good accuracy
                iou=0.45,  # Lower IOU helps detect people close together
                max_det=10  # Allow up to 10 people in frame
            )

            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Class 0 is 'person' in COCO dataset
                    if int(box.cls[0]) == 0:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        confidence = float(box.conf[0].cpu().numpy())

                        # Filter by height - very permissive range
                        height = y2 - y1
                        width = x2 - x1

                        # Basic sanity checks
                        if height < self.min_height or height > self.max_height:
                            continue

                        # Aspect ratio check - people are taller than wide
                        # But don't be too strict (groups can look wide)
                        aspect_ratio = height / max(width, 1)
                        if aspect_ratio < 0.5:  # Very permissive
                            continue

                        detections.append((x1, y1, x2, y2, confidence))

            return detections

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def draw_detections(self, frame, detections):
        """
        Draw bounding boxes on frame for visualization
        """
        for (x1, y1, x2, y2, conf) in detections:
            # Green box for detected person
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # Confidence label
            label = f"Person {conf:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        return frame
