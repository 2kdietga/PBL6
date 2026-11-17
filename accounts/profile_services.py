from django.db import transaction
from .models import User, DriverProfile, FaceProfile, DriverLicense
from .media_services import extract_embedding, upload_image, delete_images
from .concurrency import require_revision


def save_profile(form, user):
    avatar = form.cleaned_data.get('avatar')
    extras = form.cleaned_data.get('extra_images') or []
    clear_extras = form.cleaned_data.get('clear_extra_images', False)
    new_ids = []
    uploaded_extras = []
    try:
        vector = extract_embedding([avatar]) if avatar else None
        if avatar:
            url, public_id = upload_image(avatar, 'faces')
            new_ids.append(public_id)
        for image in extras:
            extra_vector = extract_embedding([image])
            extra_url, extra_id = upload_image(image, 'faces')
            new_ids.append(extra_id)
            uploaded_extras.append(dict(url=extra_url, public_id=extra_id, embedding=extra_vector))
        with transaction.atomic():
            User.objects.select_for_update().get(pk=user.pk)
            profile = form.save(commit=False)
            existing = DriverProfile.objects.select_for_update().filter(user=user).first()
            require_revision(form.cleaned_data.get('version'), existing)
            if existing:
                profile.pk = existing.pk
                profile.approval_status = existing.approval_status
            profile.user = user
            if not profile.pk or profile.approval_status == 'REJECTED' or {'full_name', 'date_of_birth', 'phone', 'address'} & set(form.changed_data):
                profile.approval_status = 'PENDING'
            profile.save()
            if avatar or extras or (clear_extras and FaceProfile.objects.filter(driver=profile).exists()):
                face = FaceProfile.objects.select_for_update().filter(driver=profile).first()
                old_ids = [face.cloudinary_public_id] if face and avatar else []
                if face is None:
                    face = FaceProfile(driver=profile)
                if avatar:
                    face.face_image_url = url
                    face.cloudinary_public_id = public_id
                    face.embedding = vector
                if extras or clear_extras:
                    old_ids.extend(item['public_id'] for item in face.extra_images)
                    face.extra_images = uploaded_extras
                face.approval_status = 'PENDING'
                face.save()
                transaction.on_commit(lambda: delete_images(old_ids))
            profile.refresh_from_db()
        return profile
    except Exception:
        delete_images(new_ids)
        raise


def save_license(form, driver):
    new_ids, uploaded = [], {}
    try:
        for side in ('front', 'back'):
            image = form.cleaned_data.get(side + '_image')
            if image:
                uploaded[side] = upload_image(image, 'licenses')
                new_ids.append(uploaded[side][1])
        with transaction.atomic():
            type(driver).objects.select_for_update().get(pk=driver.pk)
            previous = DriverLicense.objects.select_for_update().filter(driver=driver).first()
            require_revision(form.cleaned_data.get('version'), previous)
            saved = form.save(commit=False)
            saved.driver, saved.status = driver, 'PENDING'
            old_ids = []
            # Preserve the latest unchanged side, even if another request updated it.
            if previous:
                saved.pk = previous.pk
            for side in ('front', 'back'):
                if side in uploaded:
                    if previous: old_ids.append(getattr(previous, side + '_image_public_id'))
                    setattr(saved, side + '_image_url', uploaded[side][0])
                    setattr(saved, side + '_image_public_id', uploaded[side][1])
                elif previous:
                    setattr(saved, side + '_image_url', getattr(previous, side + '_image_url'))
                    setattr(saved, side + '_image_public_id', getattr(previous, side + '_image_public_id'))
            saved.save()
            transaction.on_commit(lambda: delete_images(old_ids))
        return saved
    except Exception:
        delete_images(new_ids)
        raise
