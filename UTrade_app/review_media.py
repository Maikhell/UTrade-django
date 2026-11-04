"""
UTrade_app/review_media.py   (next to models.py)

Validation + Cloudinary upload for the photos / short video a buyer can attach to a
PRODUCT rating. Every rule is enforced here on the server; the JavaScript in
rating_picker.html only gives faster feedback.

Rules (edit the constants to change them):
  - up to MAX_FILES files per rating
  - photos: JPG / PNG / WebP, up to 10 MB each (checked with Pillow, not just the name)
  - at most ONE video: MP4 / MOV / M4V / WebM, up to 25 MB and MAX_VIDEO_SECONDS long
    (the length comes from Cloudinary after upload; a too-long video is deleted again)
"""
import logging

from .models import ReviewMedia

logger = logging.getLogger(__name__)

MAX_FILES = 3
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 25 * 1024 * 1024
MAX_VIDEO_SECONDS = 8
DURATION_TOLERANCE = 0.5          # seconds; containers round lengths differently

IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}
VIDEO_EXTS = {'mp4', 'mov', 'm4v', 'webm'}
CLOUDINARY_FOLDER = 'utrade/review_media'


class MediaRejected(Exception):
    """The files break a rule (too big, too long, wrong type...). The message is user-facing."""


# ---------------------------------------------------------------- validation
def _ext(name):
    return name.rsplit('.', 1)[-1].lower() if name and '.' in name else ''


def _classify(f):
    ctype = (getattr(f, 'content_type', '') or '').lower()
    if ctype.startswith('image/'):
        return 'image'
    if ctype.startswith('video/') or _ext(f.name) in VIDEO_EXTS:
        return 'video'
    return None


def _is_valid_image(f):
    try:
        from PIL import Image
        img = Image.open(f)
        fmt = img.format
        img.verify()
    except Exception:
        return False
    finally:
        f.seek(0)
    return fmt in IMAGE_FORMATS


def _looks_like_video(f):
    """MP4 / MOV have 'ftyp' at byte 4; WebM starts with the EBML header."""
    head = f.read(12)
    f.seek(0)
    return len(head) >= 12 and (head[4:8] == b'ftyp' or head[:4] == b'\x1a\x45\xdf\xa3')


def validate(files):
    """Returns [(file, 'image'|'video'), ...] (video first) or raises MediaRejected."""
    files = [f for f in files if f]
    if not files:
        return []
    if len(files) > MAX_FILES:
        raise MediaRejected(f"You can add up to {MAX_FILES} photos or videos.")

    checked, videos = [], 0
    for f in files:
        kind = _classify(f)
        if kind == 'image':
            if f.size > MAX_IMAGE_BYTES:
                raise MediaRejected(f"“{f.name}” is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
            if not _is_valid_image(f):
                raise MediaRejected(f"“{f.name}” is not a valid JPG, PNG or WebP photo.")
        elif kind == 'video':
            videos += 1
            if videos > 1:
                raise MediaRejected("Please add only one video.")
            if f.size > MAX_VIDEO_BYTES:
                raise MediaRejected(f"The video is larger than {MAX_VIDEO_BYTES // (1024 * 1024)} MB.")
            if _ext(f.name) not in VIDEO_EXTS or not _looks_like_video(f):
                raise MediaRejected("The video must be an MP4, MOV or WebM file.")
        else:
            raise MediaRejected(f"“{f.name}” is not a photo or a video.")
        checked.append((f, kind))

    checked.sort(key=lambda pair: 0 if pair[1] == 'video' else 1)   # video first: it is the one that can fail
    return checked


# ---------------------------------------------------------------- upload
def _destroy(items):
    try:
        import cloudinary.uploader
    except ImportError:
        return
    for item in items:
        try:
            cloudinary.uploader.destroy(item['public_id'], resource_type=item['media_type'])
        except Exception:
            logger.exception('Could not delete uploaded review media %s', item.get('public_id'))


def _upload(checked):
    """
    Uploads validated files. Raises MediaRejected (e.g. video too long) or
    RuntimeError (Cloudinary unavailable). Never leaves half a batch behind.
    """
    try:
        import cloudinary.uploader
        import cloudinary.utils
    except ImportError as exc:
        raise RuntimeError('cloudinary is not installed') from exc

    items = []
    try:
        for f, kind in checked:
            if kind == 'video':
                res = cloudinary.uploader.upload(
                    f, resource_type='video', folder=CLOUDINARY_FOLDER, timeout=90,
                )
                duration = res.get('duration')
                if duration is None or duration > MAX_VIDEO_SECONDS + DURATION_TOLERANCE:
                    cloudinary.uploader.destroy(res['public_id'], resource_type='video')
                    if duration is None:
                        raise MediaRejected("We couldn't read the length of that video. Please try another one.")
                    raise MediaRejected(
                        f"The video is {duration:.0f} seconds long. The limit is {MAX_VIDEO_SECONDS} seconds."
                    )
                try:   # always serve an MP4 so it plays in every browser
                    url = cloudinary.utils.cloudinary_url(
                        res['public_id'], resource_type='video', format='mp4', secure=True
                    )[0]
                except Exception:
                    url = res['secure_url']
                items.append({
                    'media_type': 'video', 'url': url, 'public_id': res['public_id'],
                    'duration': float(duration), 'size_bytes': f.size,
                })
            else:
                res = cloudinary.uploader.upload(
                    f, resource_type='image', folder=CLOUDINARY_FOLDER, timeout=60,
                    transformation=[{'width': 1600, 'height': 1600, 'crop': 'limit', 'quality': 'auto'}],
                )
                items.append({
                    'media_type': 'image', 'url': res['secure_url'], 'public_id': res['public_id'],
                    'duration': None, 'size_bytes': f.size,
                })
    except MediaRejected:
        _destroy(items)
        raise
    except Exception as exc:
        _destroy(items)
        raise RuntimeError('Cloudinary upload failed') from exc
    return items


def prepare_media(files):
    """
    Call BEFORE saving the rating.
      returns (items, warning)
      raises MediaRejected when a rule is broken -> do not save anything, show the message
    If Cloudinary itself is unavailable it returns ([], warning) so the rating is still saved.
    """
    checked = validate(files)
    if not checked:
        return [], ''
    try:
        return _upload(checked), ''
    except MediaRejected:
        raise
    except RuntimeError:
        logger.exception('Review media upload failed')
        return [], "Your rating was saved, but the photo/video couldn't be uploaded right now."


def attach_media(reviews, items):
    """Attach the uploaded files to every product Review created for this order."""
    if not items or not reviews:
        return
    ReviewMedia.objects.bulk_create([
        ReviewMedia(
            review=review,
            media_type=item['media_type'],
            url=item['url'],
            public_id=item['public_id'],
            duration=item['duration'],
            size_bytes=item['size_bytes'],
        )
        for review in reviews
        for item in items
    ])