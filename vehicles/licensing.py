"""Vehicle and licence classes under Article 57, Law 36/2024/QH15.

Scope: ordinary rigid trucks and passenger vehicles, without heavy trailers.
Gross design mass is deliberately separate from cargo load capacity.
"""
CLASSES = ('B', 'C1', 'C', 'D1', 'D2', 'D')
EXTENDED_CLASSES = {'BE': 'B', 'C1E': 'C1', 'CE': 'C',
                    'D1E': 'D1', 'D2E': 'D2', 'DE': 'D'}


def required_license_class(category, gross_weight=None, passengers=None, sleeper=False):
    if category == 'TRUCK':
        if gross_weight is None or gross_weight <= 0:
            return None
        return 'B' if gross_weight <= 3500 else 'C1' if gross_weight <= 7500 else 'C'
    if category == 'BUS':
        if passengers is None or passengers <= 0:
            return None
        if sleeper:
            return 'D'
        return 'B' if passengers <= 8 else 'D1' if passengers <= 16 else 'D2' if passengers <= 29 else 'D'
    return None


def license_covers(held, required):
    held = (held or '').strip().upper()
    held = EXTENDED_CLASSES.get(held, held)
    return held in CLASSES and required in CLASSES and CLASSES.index(held) >= CLASSES.index(required)


def assignment_license_error(driver, vehicle):
    required = vehicle.required_license_class
    if required is None:
        return 'Xe chưa đủ thông số để xác định hạng GPLX. Cần cập nhật thông tin xe trước khi phân công.'
    license = getattr(driver, 'driver_license', None)
    if license is None:
        return 'Tài xế chưa có GPLX.'
    if license.license_standard != 'VN_2025':
        return 'Cần xác nhận GPLX thuộc hệ hạng từ 2025 trong hồ sơ tài xế trước khi phân công. Chưa hỗ trợ bằng theo hệ cũ.'
    if not license_covers(license.license_class, required):
        return f'Xe {vehicle.license_plate} yêu cầu GPLX hạng {required} hoặc hạng bao gồm quyền lái tương ứng; tài xế có hạng {license.license_class}.'
    return None
