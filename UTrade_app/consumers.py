import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatMessage, Conversation


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Check if user is authenticated
        if not self.scope.get('user') or self.scope['user'].is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name, self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_content = data.get('message', '').strip()
            attachment_url = data.get('attachment_url') or ''
            attachment_type = data.get('attachment_type') or ''

            # Allow pure media messages (no text) or pure text messages
            if not message_content and not attachment_url:
                return

            user = self.scope['user']

            # Save message safely (now accepts optional attachment fields)
            saved_msg = await self.save_message(
                user,
                self.conversation_id,
                message_content,
                attachment_url=attachment_url,
                attachment_type=attachment_type,
            )
            if not saved_msg:
                # Conversation no longer exists / was deleted
                await self.send(
                    text_data=json.dumps(
                        {'error': 'Conversation no longer exists.'}
                    )
                )
                return

            # Safe user name evaluation
            user_name = (
                user.get_short_name()
                if callable(getattr(user, 'get_short_name', None))
                else getattr(user, 'username', 'User')
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_content,
                    'user_id': user.id,
                    'user_name': user_name,
                    # NEW: forward attachment data to all clients in the room
                    'attachment_url': attachment_url,
                    'attachment_type': attachment_type,
                    'timestamp': saved_msg.timestamp.strftime('%I:%M %p'),
                },
            )
        except Exception:
            # Prevent unhandled exceptions from hanging the consumer loop
            pass

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps({
                'message': event['message'],
                'user_id': event['user_id'],
                'user_name': event.get('user_name', ''),
                # NEW: include attachment fields so the frontend can render them
                'attachment_url': event.get('attachment_url', ''),
                'attachment_type': event.get('attachment_type', ''),
                'timestamp': event.get('timestamp', 'Just now'),
            })
        )

    @database_sync_to_async
    def save_message(self, user, conversation_id, content,
                     attachment_url='', attachment_type=''):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            return ChatMessage.objects.create(
                conversation=conversation,
                user=user,
                content=content,
                # NEW fields (must exist on the ChatMessage model)
                attachment=attachment_url or None,
                attachment_type=attachment_type or '',
            )
        except (Conversation.DoesNotExist, Exception):
            return None