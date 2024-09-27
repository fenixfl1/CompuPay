import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):

    def __init__(self):
        super().__init__()
        self.room_group_name = "notification"
        self.room_name = "notification"

    async def connect(self):
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
        await self.send(text_data="Hola mundo, ahora estas conectado.")

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        print("*" * 75)
        print(f"Code: {code}")
        print("*" * 75)

    async def receive(self, text_data=None, bytes_data=None):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        print("*" * 75)
        print(f"Message: {text_data}")
        print("*" * 75)

        await self.channel_layer.group_send(
            self.room_group_name, {"type": "notification.message", "message": message}
        )

    async def notification_message(self, event):
        message = event["message"]

        await self.send(text_data=json.dumps({"message": message}))
