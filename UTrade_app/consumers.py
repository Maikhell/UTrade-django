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
      if not message_content:
        return

      user = self.scope['user']

      # Save message safely
      saved_msg = await self.save_message(
          user, self.conversation_id, message_content
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
          },
      )
    except Exception as e:
      # Prevent unhandled exceptions from hanging the consumer loop
      pass

  async def chat_message(self, event):
    await self.send(
        text_data=json.dumps({
            'message': event['message'],
            'user_id': event['user_id'],
            'user_name': event['user_name'],
        })
    )

  @database_sync_to_async
  def save_message(self, user, conversation_id, content):
    try:
      conversation = Conversation.objects.get(id=conversation_id)
      return ChatMessage.objects.create(
          conversation=conversation, user=user, content=content
      )
    except (Conversation.DoesNotExist, Exception):
      return None