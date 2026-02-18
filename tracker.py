import numpy as np
from scipy.spatial import distance as dist
from collections import OrderedDict
import config
import logging

logger = logging.getLogger(__name__)


class PersonTracker:
    """
    Tracks persons across frames and counts line crossings
    Simple and reliable - no memory system, just track current people
    """

    def __init__(self, line_position=None, count_direction='down'):
        self.next_object_id = 0
        self.objects = OrderedDict()  # {id: centroid}
        self.disappeared = OrderedDict()  # {id: frame_count}
        self.counted = set()  # IDs that crossed the line

        # Track previous positions to detect direction
        self.prev_positions = OrderedDict()  # {id: previous_y}

        self.max_disappeared = config.MAX_DISAPPEARED
        self.max_distance = config.MAX_DISTANCE

        # Counting line (horizontal line at % of frame height)
        self.line_position = line_position or config.LINE_POSITION
        self.line_y = None

        # Direction: 'down' = top to bottom (entering), 'up' = bottom to top (exiting), 'both' = both directions
        self.count_direction = count_direction

        self.total_count = 0
        self.current_detections = 0

    def set_line_position(self, frame_height):
        """Set the counting line position based on frame height"""
        self.line_y = int(frame_height * self.line_position)
        logger.info(f"Counting line set at y={self.line_y}")

    def register(self, centroid):
        """Register a new object with next available ID"""
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        # Store y position
        self.prev_positions[self.next_object_id] = centroid[1]
        self.next_object_id += 1

    def deregister(self, object_id):
        """Remove an object that disappeared"""
        del self.objects[object_id]
        del self.disappeared[object_id]
        if object_id in self.prev_positions:
            del self.prev_positions[object_id]
        # Remove from counted if they disappear before crossing
        if object_id in self.counted:
            self.counted.discard(object_id)

    def update(self, detections):
        """
        Update tracker with new detections
        Returns: Dictionary of tracked objects {id: (centroid, bbox)}
        """
        self.current_detections = len(detections)

        # If no detections, mark all as disappeared
        if len(detections) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1

                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            return {}

        # Get centroids and bboxes from detections
        input_centroids = np.zeros((len(detections), 2), dtype="int")
        rects = []

        for i, (x1, y1, x2, y2, conf) in enumerate(detections):
            cX = int((x1 + x2) / 2.0)
            cY = int((y1 + y2) / 2.0)
            input_centroids[i] = (cX, cY)
            rects.append((x1, y1, x2, y2))

        # If no existing objects, register all
        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i])

        else:
            # Match existing objects with new detections
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())

            # Calculate distances between existing and new centroids
            D = dist.cdist(np.array(object_centroids), input_centroids)

            # Find minimum distance matches
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue

                # Check if distance is reasonable
                if D[row, col] > self.max_distance:
                    continue

                object_id = object_ids[row]

                # Update previous position before updating current
                self.prev_positions[object_id] = self.objects[object_id][1]

                # Update current position
                self.objects[object_id] = input_centroids[col]
                self.disappeared[object_id] = 0

                used_rows.add(row)
                used_cols.add(col)

            # Handle disappeared objects
            unused_rows = set(range(D.shape[0])) - used_rows
            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1

                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            # Register new objects
            unused_cols = set(range(D.shape[1])) - used_cols
            for col in unused_cols:
                self.register(input_centroids[col])

        # Build return dictionary with bboxes
        tracked = {}
        for object_id in list(self.objects.keys()):
            # Find matching bbox for this object
            centroid = self.objects[object_id]
            # Match to closest detection
            min_dist = float('inf')
            best_rect = None

            for i, det_centroid in enumerate(input_centroids):
                d = np.linalg.norm(centroid - det_centroid)
                if d < min_dist and i < len(rects):
                    min_dist = d
                    best_rect = rects[i]

            if best_rect is not None:
                tracked[object_id] = (tuple(centroid), best_rect)

        return tracked

    def check_line_crossing(self, object_id, centroid, bbox):
        """
        Check if person crossed the counting line in the specified direction
        Directions:
        - 'down': top to bottom (entering from top)
        - 'up': bottom to top (entering from bottom)
        - 'both': count both directions
        Returns: True if new crossing detected
        """
        if self.line_y is None:
            return False

        # Check if already counted
        if object_id in self.counted:
            return False

        cX, cY = centroid

        # Get previous position
        if object_id not in self.prev_positions:
            self.prev_positions[object_id] = cY
            return False

        prev_y = self.prev_positions[object_id]

        crossed = False
        direction = None

        # Check for downward crossing (top to bottom)
        if prev_y < self.line_y and cY >= self.line_y:
            direction = 'down'
            if self.count_direction in ['down', 'both']:
                crossed = True

        # Check for upward crossing (bottom to top)
        elif prev_y > self.line_y and cY <= self.line_y:
            direction = 'up'
            if self.count_direction in ['up', 'both']:
                crossed = True

        if crossed:
            self.counted.add(object_id)
            self.total_count += 1

            direction_text = "↓ DOWN (entering)" if direction == 'down' else "↑ UP (exiting)"
            logger.info(
                f"✓ Person {object_id} crossed line {direction_text} (y: {prev_y} → {cY}). Total: {self.total_count}")
            return True

        return False

    def reset_count(self):
        """Reset total count (admin action)"""
        old_count = self.total_count
        self.total_count = 0
        self.counted.clear()
        logger.info(f"Count reset from {old_count} to 0")

    def get_stats(self):
        """Get current statistics"""
        return {
            'total_count': self.total_count,
            'current_tracking': len(self.objects),
            'current_detections': self.current_detections
        }
