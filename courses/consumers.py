from channels.generic.websocket import AsyncWebsocketConsumer


class CourseChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close(code=4403)
            return
        await self.accept()
        await self.send(text_data="Connected to course chat.")
