import os
from datetime import datetime

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'counts')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
MODEL_DIR = os.path.join(BASE_DIR, 'models')

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# Camera settings
CAMERA_URL = "<your_camera_stream_url>"

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FPS = 30  # Increase if we need detection of fast movement

# Detection settings
CONFIDENCE_THRESHOLD = 0.35  # Lower to catch more people
# people far from camera appear small.Minimum bounding box height (in pixels)
MIN_PERSON_HEIGHT = 60
# Higher for people close to camera,Max bounding box height (in pixels)
MAX_PERSON_HEIGHT = 700

# Tracking settings
MAX_DISAPPEARED = 15  # Reduced - don't wait too long (0.5 seconds at 30 FPS)
MAX_DISTANCE = 120  # Increased significantly for fast-moving people

# Counting line position (percentage from top)
LINE_POSITION = 0.6  # Line at 60% from top of frame

# Counting direction - CHOOSE ONE:
# 'down' = Count only people entering from top
# 'up' = Count only people entering from bottom
# 'both' = Count both directions
COUNT_DIRECTION = 'down'  # Only count people entering

# Data storage settings
SAVE_INTERVAL = 3600  # Save every hour
BACKUP_INTERVAL = 300  # Backup every 5 minutes

# CSV file naming


def get_csv_filename():
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(DATA_DIR, f"Temple_Count_{today}.csv")


def get_backup_filename():
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return os.path.join(DATA_DIR, f"Backup_{now}.csv")



SESSION_TIMEOUT = 3600

# System settings
DEBUG_MODE = False
LOG_LEVEL = "INFO"
MAX_LOG_SIZE = 10 * 1024 * 1024

# PERFORMANCE TUNING FOR GPU
FRAME_SKIP = 1
