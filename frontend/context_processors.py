from accounts.models import FaceProfile, FaceProcessingJob


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
    job = (None if request.user.is_superuser or request.user.role == 'ADMIN'
           else FaceProcessingJob.objects.filter(driver__user=request.user).first())
    return {'account_face': face, 'account_face_job': job}
