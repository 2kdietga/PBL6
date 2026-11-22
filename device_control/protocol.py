import math
import re

PARAMETERS = {
    'DROWSY_CLOSED_SECONDS': (1.5, 1.0, 3.0, 'Nhắm mắt (giây)'),
    'YAWN_MIN_SECONDS': (0.7, 0.5, 1.5, 'Ngáp (giây)'),
    'YAW_AWAY_DEG': (35.0, 25.0, 50.0, 'Quay đầu (độ)'),
    'PITCH_AWAY_DOWN_DEG': (30.0, 20.0, 45.0, 'Cúi đầu (độ)'),
    'LOOK_AWAY_SECONDS': (2.0, 1.5, 4.0, 'Nhìn ra ngoài (giây)'),
    'OBJECT_PHONE_NEAR_SECONDS': (0.9, 0.6, 2.0, 'Điện thoại ở gần (giây)'),
    'PHONE_INTERACTION_MIN_SECONDS': (1.2, 0.8, 2.5, 'Tương tác điện thoại (giây)'),
    'OBJECT_CONF': (0.30, 0.25, 0.60, 'Độ tin cậy vật thể'),
}


def defaults():
    return {key: spec[0] for key, spec in PARAMETERS.items()}


def validate_parameters(values):
    if not isinstance(values, dict) or set(values) != set(PARAMETERS):
        raise ValueError('Cần đủ đúng 8 ngưỡng AI.')
    for key, value in values.items():
        if type(value) not in (int, float) or not math.isfinite(value) or not PARAMETERS[key][1] <= value <= PARAMETERS[key][2]:
            raise ValueError(f'{key}: giá trị ngoài giới hạn.')
    return values


def valid_device_code(code):
    return isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', code) is not None


def valid_version(value):
    return type(value) is int and 0 <= value <= 2147483647
