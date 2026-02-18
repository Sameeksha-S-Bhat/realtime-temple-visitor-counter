from flask import Flask, render_template, Response, jsonify, request, send_file
from flask_cors import CORS
import cv2
import threading
import time
from datetime import datetime
import pandas as pd
import logging
import config
from detector import PersonDetector
from tracker import PersonTracker

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{config.LOGS_DIR}/temple_counter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
CORS(app)

# Global state


class CounterState:
    def __init__(self):
        self.is_running = False
        self.camera = None
        self.detector = None
        self.tracker = None
        self.current_frame = None
        self.lock = threading.Lock()
        self.hourly_data = []
        self.last_save_time = time.time()
        self.camera_url = None
        self.last_frame_time = time.time()
        self.fps = 0


state = CounterState()


def initialize_system():
    """Initialize detection and tracking systems"""
    try:
        logger.info("Initializing AI detector...")
        state.detector = PersonDetector()

        logger.info("Initializing tracker...")
        state.tracker = PersonTracker(count_direction=config.COUNT_DIRECTION)

        logger.info("System initialized successfully!")
        return True
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return False


def connect_camera(camera_url):
    """Connect to camera (phone or CCTV)"""
    try:
        logger.info(f"Connecting to camera: {camera_url}")
        cap = cv2.VideoCapture(camera_url)

        if not cap.isOpened():
            logger.error("Failed to open camera")
            return None

        # Set camera properties for better detection
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)  # Higher FPS for smooth detection
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer lag

        logger.info("Camera connected successfully!")
        return cap
    except Exception as e:
        logger.error(f"Camera connection error: {e}")
        return None


def save_hourly_data():
    """Save hourly count data to CSV"""
    try:
        now = datetime.now()
        current_hour = now.strftime("%H:00")
        count = state.tracker.total_count if state.tracker else 0

        # Add to hourly data
        state.hourly_data.append({
            'Time': current_hour,
            'Count': count,
            'Timestamp': now.strftime("%Y-%m-%d %H:%M:%S")
        })

        # Save to CSV
        df = pd.DataFrame(state.hourly_data)
        csv_file = config.get_csv_filename()
        df.to_csv(csv_file, index=False)

        logger.info(f"Hourly data saved: {current_hour} - {count} people")

    except Exception as e:
        logger.error(f"Failed to save hourly data: {e}")


def processing_loop():
    """Main video processing loop - Process EVERY frame for GPU"""
    logger.info("Processing loop started")
    frame_count = 0
    fps_counter = 0
    fps_start_time = time.time()

    while state.is_running:
        try:
            if state.camera is None:
                time.sleep(0.1)
                continue

            ret, frame = state.camera.read()
            if not ret or frame is None:
                logger.warning("Failed to read frame")
                time.sleep(0.1)
                continue

            frame_count += 1
            fps_counter += 1

            # Calculate FPS every second
            current_time = time.time()
            if current_time - fps_start_time >= 1.0:
                state.fps = fps_counter
                fps_counter = 0
                fps_start_time = current_time

            # Set line position on first frame
            if state.tracker.line_y is None:
                state.tracker.set_line_position(frame.shape[0])

            # NO FRAME SKIPPING - Process every frame
            # Detect persons
            detections = state.detector.detect(frame)

            # Update tracker
            tracked_objects = state.tracker.update(detections)

            # Check line crossings
            for object_id, (centroid, bbox) in tracked_objects.items():
                state.tracker.check_line_crossing(object_id, centroid, bbox)

            # Get stats
            stats = state.tracker.get_stats()

            # Draw counting line
            if state.tracker.line_y:
                # Different colors based on direction
                line_color = (0, 0, 255) if config.COUNT_DIRECTION == 'down' else (
                    255, 0, 0) if config.COUNT_DIRECTION == 'up' else (255, 255, 0)
                cv2.line(frame, (0, state.tracker.line_y),
                         (frame.shape[1], state.tracker.line_y),
                         line_color, 3)

                # Direction arrow and text
                direction_text = "COUNTING LINE - ↓ ENTER FROM TOP" if config.COUNT_DIRECTION == 'down' else "COUNTING LINE - ↑ ENTER FROM BOTTOM" if config.COUNT_DIRECTION == 'up' else "COUNTING LINE - ↕ BOTH DIRECTIONS"
                text_size = cv2.getTextSize(
                    direction_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(frame, (5, state.tracker.line_y - 35),
                              (15 + text_size[0], state.tracker.line_y - 5), (0, 0, 0), -1)
                cv2.putText(frame, direction_text, (10, state.tracker.line_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, line_color, 2)

            # Draw detections
            for (x1, y1, x2, y2, conf) in detections:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{conf:.0%}"
                label_size = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                cv2.rectangle(frame, (x1, y1 - 20),
                              (x1 + label_size[0] + 5, y1), (0, 255, 0), -1)
                cv2.putText(frame, label, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # Draw tracking IDs
            for object_id, (centroid, bbox) in tracked_objects.items():
                cX, cY = centroid
                cv2.circle(frame, (cX, cY), 5, (255, 0, 0), -1)

                id_text = f"ID:{object_id}"
                text_size = cv2.getTextSize(
                    id_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                cv2.rectangle(frame, (cX - 5, cY - 25),
                              (cX + text_size[0] + 5, cY - 5), (255, 0, 0), -1)
                cv2.putText(frame, id_text, (cX, cY - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Draw stats overlay
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, 5), (350, 110), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

            cv2.putText(frame, f"Total Count: {stats['total_count']}", (15, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Currently Tracking: {stats['current_tracking']}", (15, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(frame, f"Detections: {stats['current_detections']} | FPS: {state.fps}", (15, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            # Store frame
            with state.lock:
                state.current_frame = frame.copy()

            # Check if time to save hourly data
            if current_time - state.last_save_time >= config.SAVE_INTERVAL:
                save_hourly_data()
                state.last_save_time = current_time

            # Small delay to prevent overwhelming the system
            time.sleep(0.01)

        except Exception as e:
            logger.error(f"Processing error: {e}")
            time.sleep(0.1)

    logger.info("Processing loop ended")


def generate_frames():
    """Generate frames for video stream"""
    while True:
        with state.lock:
            if state.current_frame is None:
                time.sleep(0.1)
                continue

            frame = state.current_frame.copy()

        # Encode with good quality
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        ret, buffer = cv2.imencode('.jpg', frame, encode_param)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/start', methods=['POST'])
def start_counting():
    """Start the counting system"""
    try:
        data = request.json
        camera_url = data.get('camera_url', config.CAMERA_URL)

        if state.is_running:
            return jsonify({'status': 'error', 'message': 'System already running'})

        # Initialize if needed
        if state.detector is None:
            if not initialize_system():
                return jsonify({'status': 'error', 'message': 'Failed to initialize'})

        # Connect camera
        state.camera = connect_camera(camera_url)
        if state.camera is None:
            return jsonify({'status': 'error', 'message': 'Failed to connect camera'})

        state.camera_url = camera_url
        state.is_running = True
        state.last_save_time = time.time()

        # Start processing thread
        thread = threading.Thread(target=processing_loop, daemon=True)
        thread.start()

        logger.info("System started successfully")
        return jsonify({'status': 'success', 'message': 'System started'})

    except Exception as e:
        logger.error(f"Start error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/api/stop', methods=['POST'])
def stop_counting():
    """Stop the counting system"""
    try:
        state.is_running = False

        if state.camera:
            state.camera.release()
            state.camera = None

        # Save final data
        save_hourly_data()

        logger.info("System stopped")
        return jsonify({'status': 'success', 'message': 'System stopped'})

    except Exception as e:
        logger.error(f"Stop error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/api/reset', methods=['POST'])
def reset_count():
    """Reset the count"""
    try:
        if state.tracker:
            state.tracker.reset_count()
            state.hourly_data = []

        logger.info("Count reset")
        return jsonify({'status': 'success', 'message': 'Count reset'})

    except Exception as e:
        logger.error(f"Reset error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/api/stats')
def get_stats():
    """Get current statistics"""
    try:
        if state.tracker:
            stats = state.tracker.get_stats()
            stats['is_running'] = state.is_running
            stats['hourly_data'] = state.hourly_data[-10:]
            return jsonify(stats)
        else:
            return jsonify({
                'total_count': 0,
                'current_tracking': 0,
                'current_detections': 0,
                'is_running': False,
                'hourly_data': []
            })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': str(e)})


@app.route('/api/download')
def download_csv():
    """Download today's CSV file"""
    try:
        csv_file = config.get_csv_filename()
        return send_file(csv_file, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)})


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("TEMPLE VISITOR COUNTER SYSTEM")
    logger.info("=" * 50)

    # Initialize system
    initialize_system()

    # Start Flask server
    logger.info("Starting web server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=config.DEBUG_MODE, threaded=True)
