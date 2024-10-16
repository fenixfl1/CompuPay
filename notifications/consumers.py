import json
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from users.models import User
from .models import Notification

connected_users = {}


class NotificationConsumer(AsyncWebsocketConsumer):

    def __init__(self):
        super().__init__()
        self.username: str = ""

    async def connect(self):
        self.username = self.scope["url_route"]["kwargs"]["username"]
        connected_users[self.username] = self.channel_name

        await self.accept()

        user = await sync_to_async(User.objects.get)(username=self.username)
        unreaded_notification = await sync_to_async(list)(
            Notification.objects.filter(receiver=user, is_read=False).values_list(
                "message", flat=True
            )
        )

        for message in unreaded_notification:
            await self.send(
                text_data=json.dumps({"message": message, "type": "offtime"})
            )

    async def disconnect(self, code):
        for group in self.groups:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data: dict = json.loads(text_data)
            message: str = data.get("message", "")
            receivers: list[str] = data.get("receivers", [])

            sender = await sync_to_async(User.objects.get)(username=self.username)

            print("*" * 75)
            print(f"Receivers: {str(receivers)} \n Sender: {sender.username}")
            print("*" * 75)

            if not receivers:
                receivers = [self.username]

            for receiver in receivers:
                receiver = await sync_to_async(User.objects.get)(username=receiver)

                await sync_to_async(Notification.objects.create)(
                    receiver=receiver, sender=sender, message=message
                )

                connected_user = connected_users.get(receiver.username, None)

                print("*" * 75)
                print(f"Connected Users: {connected_user}")
                print("*" * 75)

                if connected_user:
                    await self.channel_layer.send(
                        connected_user,
                        {
                            "type": "notification.message",
                            "message": json.dumps(
                                {"message": message, "type": "ontime"}
                            ),
                        },
                    )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid data format"}))

    async def notification_message(self, event):
        message = event["message"]

        await self.send(text_data=json.dumps({"message": message}))
