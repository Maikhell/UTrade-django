from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from ..models import Conversation, ChatMessage, Product
from django.db.models import Q
from django.contrib import messages  

@login_required
def start_chat(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if product.seller == request.user:
        messages.warning(request, "You cannot message yourself about your own product.")
        return redirect('product.list') 

    conversation, created = Conversation.objects.get_or_create(
        product=product,
        buyer=request.user,
        seller=product.seller
    )
    
    return redirect('chat_view', conversation_id=conversation.id)

@login_required
def inbox(request):
    conversations = Conversation.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user)
    ).order_by('-created_at')
    
    storage = messages.get_messages(request)
    for _ in storage:
        pass 
        
    return render(request, 'UTrade_app/chat/inbox.html', {'conversations': conversations})

@login_required
def chat_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Security: Ensure only the buyer or seller can see the chat
    if request.user != conversation.buyer and request.user != conversation.seller:
        return redirect('inbox')

    # Identify the OTHER user (the one you are NOT)
    if request.user == conversation.buyer:
        other_user = conversation.seller
    else:
        other_user = conversation.buyer

    # 1. Clear any stuck messages from the previous page (like start_chat)
    storage = messages.get_messages(request)
    for _ in storage:
        pass

    # 2. Set the notification for the OTHER user's name
    session_key = f'chat_notif_{conversation.id}'
    if not request.session.get(session_key):
        # We use other_user here, NOT request.user
        messages.success(request, f"You are chatting with {other_user.first_name}")
        request.session[session_key] = True 
        
    chat_messages = conversation.messages.all().order_by('timestamp')

    return render(request, 'UTrade_app/chat/chat.html', {
        'conversation': conversation,
        'messages': chat_messages, 
        'other_user': other_user  
    })