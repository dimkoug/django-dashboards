import json

from channels.generic.websocket import AsyncWebsocketConsumer


def group_for(user_id) -> str:
    return f'notifications_{user_id}'


class NotificationConsumer(AsyncWebsocketConsumer):
    """Per-user notification channel. Joined group: notifications_<user_id>."""

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.close()
            return
        self.group_name = group_for(user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name)

    # Channel-layer event handler (type: "notify").
    async def notify(self, event):
        await self.send(text_data=json.dumps(event['data']))
