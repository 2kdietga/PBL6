from accounts.models import FaceProfile


def account_face(request):
    """Expose the signed-in user's current face image to the shared header."""
    if not request.user.is_authenticated:
        return {'account_face': None}
    face = (
        FaceProfile.objects
        .filter(driver__user=request.user)
        .only('face_image_url', 'approval_status')
        .first()
    )
    return {'account_face': face}
