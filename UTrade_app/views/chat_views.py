import json
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.contrib import messages 
from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
import cloudinary.uploader
from django.conf import settings

from ..models import Conversation, ChatMessage, UserReport, User, Product
from ..utils import log_action




MAX_FILE_BYTES = 9 * 1024 * 1024          # 9 MB
MAX_VIDEO_SECONDS = 3

@login_required
@require_POST
def upload_chat_attachment(request):
    """
    Accepts a single image or short video, validates size/duration,
    uploads to Cloudinary and returns the secure URL.
    """
    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'message': 'No file provided'}, status=400)

    f = request.FILES['file']

    # size check
    if f.size > MAX_FILE_BYTES:
        return JsonResponse({'success': False, 'message': 'File exceeds 9 MB limit'}, status=400)

    content_type = f.content_type or ''
    is_image = content_type.startswith('image/')
    is_video = content_type.startswith('video/')

    if not (is_image or is_video):
        return JsonResponse({'success': False, 'message': 'Only images and videos allowed'}, status=400)

    # Cloudinary upload options
    upload_options = {
        'folder': f'utrade/chat/{request.user.id}',
        'resource_type': 'auto',          # auto-detect image/video
        'overwrite': False,
        'unique_filename': True,
    }

    if is_video:
        # enforce max 3 seconds at upload time (Cloudinary can also trim)
        upload_options['eager'] = [
            {'duration': MAX_VIDEO_SECONDS}   # Cloudinary will truncate if longer
        ]

    try:
        result = cloudinary.uploader.upload(f, **upload_options)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({
        'success': True,
        'url': result['secure_url'],
        'public_id': result['public_id'],
        'resource_type': result['resource_type'],
        'format': result.get('format'),
        'bytes': result.get('bytes'),
        'duration': result.get('duration'),   # only present for video
    })
    
def report_conversation(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in (conversation.buyer, conversation.seller):
        return JsonResponse({'success': False, 'message': 'Not allowed'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    reason = (data.get('reason') or '').strip()
    details = (data.get('details') or '').strip()
    if not reason:
        return JsonResponse({'success': False, 'message': 'Reason required'}, status=400)

    reported = conversation.seller if request.user == conversation.buyer else conversation.buyer

    # Prevent spam duplicate pending reports
    if UserReport.objects.filter(
        conversation=conversation,
        reporter=request.user,
        status='pending',
    ).exists():
        return JsonResponse({'success': False, 'message': 'You already have a pending report for this chat.'}, status=400)

    UserReport.objects.create(
        conversation=conversation,
        reporter=request.user,
        reported_user=reported,
        reason=reason,
        details=details,
    )
    return JsonResponse({'success': True, 'message': 'Report submitted. Management will review it.'})


def is_management(user):
    return user.is_authenticated and user.user_role == 'management'


@login_required
@user_passes_test(is_management)
@require_POST
def management_suspend_user(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')
    report_id = data.get('report_id')
    days = data.get('days')  # int or "custom"
    custom_days = data.get('custom_days')
    reason = (data.get('reason') or '').strip()

    target = get_object_or_404(User, id=user_id)
    if target.user_role == 'management':
        return JsonResponse({'success': False, 'message': 'Cannot suspend management.'}, status=400)

    try:
        if days == 'custom':
            n = int(custom_days)
        else:
            n = int(days)
        if n < 1:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Invalid duration'}, status=400)

    until = timezone.now() + timedelta(days=n)
    target.is_suspended = True
    target.suspension_until = until
    target.suspension_reason = reason or f'Suspended by management for {n} day(s).'
    target.save(update_fields=['is_suspended', 'suspension_until', 'suspension_reason'])

    # System DM: use a support conversation if you have one; else chat on related product
    report = None
    if report_id:
        report = UserReport.objects.filter(id=report_id).select_related('conversation').first()
        if report:
            report.status = 'resolved'
            report.reviewed_by = request.user
            report.save(update_fields=['status', 'reviewed_by', 'updated_at'])

            conv = report.conversation
            ChatMessage.objects.create(
                conversation=conv,
                user=request.user,
                content=(
                    f"🚨 SYSTEM (Management): Your account has been suspended for {n} day(s).\n"
                    f"Until: {until.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Reason: {target.suspension_reason}"
                ),
                is_read=False,
            )

    log_action(
        user=request.user,
        action='User Suspended',
        item_type='User',
        item_name=str(target),
        details=f'Suspended {n} days. Reason: {target.suspension_reason}',
    )

    return JsonResponse({'success': True, 'message': f'{target} suspended for {n} day(s).'})
@login_required
def start_chat(request, product_id):
    """
    Open (or create) a conversation about a product.

    Optional query params:
      ?from=management  – management contacting the seller about this listing
      ?ref=product      – same intent; used for system reference message
    """
    product = get_object_or_404(
        Product.objects.select_related('seller'),
        id=product_id,
    )

    # Seller cannot message themselves (management may still contact the seller)
    is_management = getattr(request.user, 'user_role', '') == 'management'
    if product.seller_id == request.user.id and not is_management:
        messages.warning(request, "You cannot message yourself about your own product.")
        return redirect('product.list')

    conversation, created = Conversation.objects.get_or_create(
        product=product,
        buyer=request.user,
        seller=product.seller,
    )

    from_mgmt = request.GET.get('from') == 'management' or request.GET.get('ref') == 'product'
    code = getattr(product, 'product_code', None) or 'N/A'

    # Auto-reference the product once when management opens the thread
    if from_mgmt and is_management:
        already = conversation.messages.filter(
            user=request.user,
            content__startswith='📌 Re: product',
        ).exists()
        if not already:
            ChatMessage.objects.create(
                conversation=conversation,
                user=request.user,
                content=(
                    f'📌 Re: product "{product.name}" '
                    f'(Code: {code})\n'
                    f'This conversation was opened from the Management dashboard.'
                ),
                is_read=False,
            )
    elif created:
        # Optional first message for normal buyers (keeps context clear)
        ChatMessage.objects.create(
            conversation=conversation,
            user=request.user,
            content=f'Hi! I\'m inquiring about "{product.name}".',
            is_read=False,
        )

    return redirect('chat_view', conversation_id=conversation.id)


@login_required
def inbox(request):
    conversations = (
        Conversation.objects.filter(
            Q(buyer=request.user) | Q(seller=request.user)
        )
        .select_related('product', 'buyer', 'seller')
        .order_by('-created_at')
    )

    # Drain flash messages so they don't stick on inbox
    storage = messages.get_messages(request)
    for _ in storage:
        pass

    return render(
        request,
        'UTrade_app/chat/inbox.html',
        {'conversations': conversations},
    )


@login_required
def chat_view(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related('product', 'buyer', 'seller'),
        id=conversation_id,
    )

    # Only buyer or seller may open this thread
    if request.user != conversation.buyer and request.user != conversation.seller:
        return redirect('inbox')

    other_user = (
        conversation.seller
        if request.user == conversation.buyer
        else conversation.buyer
    )

    # Clear leftover messages from previous page
    storage = messages.get_messages(request)
    for _ in storage:
        pass

    # One-time banner for this conversation
    session_key = f'chat_notif_{conversation.id}'
    if not request.session.get(session_key):
        display = (
            other_user.get_full_name()
            or other_user.first_name
            or other_user.username
            or other_user.student_no
        )
        messages.success(request, f"You are chatting with {display}")
        request.session[session_key] = True

    chat_messages = conversation.messages.all().order_by('timestamp')

    return render(
        request,
        'UTrade_app/chat/conversation.html',
        {
            'conversation': conversation,
            'messages': chat_messages,
            'other_user': other_user,
            'product': conversation.product,
        },
    )