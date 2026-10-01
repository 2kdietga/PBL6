"""Call from the existing NanoDet camera loop; no image files are created.

Requires requests and OpenCV on the Pi. Detection boxes are (x1, y1, x2, y2,
confidence) in ORIGINAL frame coordinates, filtered to the face class.
"""
import os
import time
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

import cv2
import requests


class BestFrameSelector:
    def __init__(self, stable_frames=6, confidence=0.7, min_iou=0.4):
        self.stable_frames = stable_frames
        self.confidence = confidence
        self.min_iou = min_iou
        self.reset()

    def reset(self):
        self.previous_box = None
        self.count = 0
        self.best = None
        self.best_score = -1
        self.window_start = None

    @staticmethod
    def iou(a, b):
        overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
        area_a = (a[2]-a[0]) * (a[3]-a[1])
        area_b = (b[2]-b[0]) * (b[3]-b[1])
        return overlap / max(1, area_a + area_b - overlap)

    def update(self, frame_bgr, face_boxes):
        """Return (full_frame_bgr, captured_at) after one stable window, else None."""
        boxes = [box for box in face_boxes if box[4] >= self.confidence]
        if len(boxes) != 1:
            self.reset()
            return None
        height, width = frame_bgr.shape[:2]
        box = boxes[0]
        box = (max(0, min(width, int(box[0]))), max(0, min(height, int(box[1]))),
               max(0, min(width, int(box[2]))), max(0, min(height, int(box[3]))))
        if box[2] <= box[0] or box[3] <= box[1]:
            self.reset()
            return None
        now = time.monotonic()
        if ((self.previous_box is not None and self.iou(box, self.previous_box) < self.min_iou)
                or (self.window_start is not None and now-self.window_start > 2)):
            self.reset()
        if self.window_start is None:
            self.window_start = now
        self.previous_box = box
        # ROI is only used to rank sharpness locally. The submitted image is full frame.
        roi = frame_bgr[box[1]:box[3], box[0]:box[2]]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        if sharpness > self.best_score:
            self.best_score = sharpness
            self.best = (frame_bgr.copy(), datetime.now(timezone.utc).isoformat())
        self.count += 1
        if self.count < self.stable_frames:
            return None
        best = self.best
        self.reset()
        return best


class FaceClient:
    def __init__(self, base_url=None, device_code=None, api_key=None):
        self.base_url = (base_url or os.environ['WEB_SERVER_URL']).rstrip('/')
        parsed_url = urlsplit(self.base_url)
        if parsed_url.scheme not in ('http', 'https') or not parsed_url.netloc:
            raise ValueError('WEB_SERVER_URL must be an HTTP or HTTPS URL')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': 'Bearer ' + (api_key or os.environ['DEVICE_API_KEY']),
        })
        # Optional compatibility for keys issued before token-only authentication.
        device_code = device_code or os.environ.get('DEVICE_CODE')
        if device_code:
            self.session.headers['X-Device-Code'] = device_code

    def context(self):
        response = self.session.get(self.base_url + '/api/v1/device/context/', timeout=(5, 10), allow_redirects=False)
        return response.status_code, response.json()

    def verify(self, frame_bgr, captured_at):
        height, width = frame_bgr.shape[:2]
        scale = min(1.0, 1280 / width, 720 / height)
        if scale < 1:
            frame_bgr = cv2.resize(frame_bgr, (max(1, int(width * scale)), max(1, int(height * scale))),
                                   interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError('JPEG encoding failed')
        jpeg_bytes = encoded.tobytes()
        if len(jpeg_bytes) > 2 * 1024 * 1024:
            raise ValueError('JPEG exceeds 2 MiB')
        # requests sets multipart boundary and Content-Length. Do not set Content-Type manually.
        response = self.session.post(
            self.base_url + '/api/v1/device/face-verifications/',
            headers={'X-Request-ID': str(uuid4())},
            data={'captured_at': captured_at},
            files={'frame': ('frame.jpg', jpeg_bytes, 'image/jpeg')},
            timeout=(5, 45), allow_redirects=False,
        )
        return response.status_code, response.json()

    def close(self):
        self.session.close()
