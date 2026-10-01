from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadhandler import FileUploadHandler


class DeviceAPIError(Exception):
    def __init__(self, code, message, status=400, action='FIX_REQUEST', retry_after=None):
        self.code, self.message, self.status = code, message, status
        self.action, self.retry_after = action, retry_after
        super().__init__(message)


class FrameUploadHandler(FileUploadHandler):
    """The sole handler for this endpoint: bounded RAM, never a temporary file."""
    def __init__(self, request, limit):
        super().__init__(request)
        self.limit = limit
        self.count = 0

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.count += 1
        if self.count != 1 or self.field_name != 'frame':
            raise DeviceAPIError('INVALID_FRAME', 'Chỉ gửi một ảnh JPEG trong trường frame.')
        if self.content_type != 'image/jpeg':
            raise DeviceAPIError('UNSUPPORTED_IMAGE', 'Ảnh phải có Content-Type image/jpeg.', 415)
        self.buffer = BytesIO()

    def receive_data_chunk(self, raw_data, start):
        if self.buffer.tell() + len(raw_data) > self.limit:
            raise DeviceAPIError('FRAME_TOO_LARGE', 'Ảnh vượt quá giới hạn 2 MiB.', 413)
        self.buffer.write(raw_data)
        return None

    def file_complete(self, file_size):
        self.buffer.seek(0)
        return InMemoryUploadedFile(self.buffer, self.field_name, 'frame.jpg',
                                    'image/jpeg', file_size, None)
