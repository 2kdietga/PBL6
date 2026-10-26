from .device_api import device_endpoint, process_face_request, reply
from .device_protocol import DeviceAPIError
from .session_services import start_session, end_session, session_data


def complete_start(request, driver):
    identity = {'verified': True, 'session_started': False, 'session_id': None,
                'driver': {'id': driver.pk, 'full_name': driver.full_name}}
    try:
        session = start_session(request.device, driver)
    except DeviceAPIError as exc:
        # Never disclose identity after device credentials have been revoked.
        if exc.code == 'DEVICE_UNAUTHORIZED':
            raise
        identity['reason_code'] = getattr(exc, 'reason_code', exc.code)
        return reply(request, exc.code, exc.message, status=exc.status,
                     action=exc.action, retry_after=exc.retry_after, data=identity)
    data = session_data(session)
    data.update(verified=True, session_started=True, reason_code=None)
    return reply(request, 'SESSION_STARTED', 'Đã bắt đầu phiên lái.', status=201, data=data)


@device_endpoint('POST')
def start(request):
    return process_face_request(request, on_verified=complete_start)


@device_endpoint('POST', require_ready=False)
def end(request, pk):
    # A stopped vehicle, suspended driver or maintenance device must still be able to close its session.
    if request.META.get('CONTENT_LENGTH', '') not in ('', '0'):
        raise DeviceAPIError('INVALID_FIELDS', 'Kết thúc phiên không nhận payload.')
    session = end_session(request.device, pk)
    return reply(request, 'SESSION_ENDED', 'Đã kết thúc phiên lái.', data=session_data(session))
