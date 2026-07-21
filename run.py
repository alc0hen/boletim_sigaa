import os
import asyncio
import websockets
from asgiref.wsgi import WsgiToAsgi
from app import create_app
from hypercorn.asyncio import serve
from hypercorn.config import Config

app = create_app()
asgi_app = WsgiToAsgi(app)


WS_URL = os.getenv("WS_URL")


async def handle_client(reader, writer):
    try:
        async with websockets.connect(WS_URL) as ws:
            async def tcp_to_ws():
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    await ws.send(data)

            async def ws_to_tcp():
                async for msg in ws:
                    writer.write(msg if isinstance(msg, bytes) else msg.encode())
                    await writer.drain()

            await asyncio.gather(tcp_to_ws(), ws_to_tcp())
    except Exception:
        pass
    finally:
        writer.close()


async def start_bridge():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 6379)
    print(f"🚀 Ponte local do Redis ativa em 127.0.0.1:6379 -> {WS_URL}")
    async with server:
        await server.serve_forever()



async def main():
    config = Config()
    config.bind = [f"0.0.0.0:{os.getenv('PORT', '5000')}"]
    config.loglevel = "debug"
    asyncio.create_task(start_bridge())
    await serve(asgi_app, config)


if __name__ == "__main__":
    asyncio.run(main())