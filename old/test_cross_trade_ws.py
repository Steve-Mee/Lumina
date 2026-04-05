import asyncio
import websockets
import json
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv("CROSSTRADE_TOKEN")

async def test():
    uri = "wss://app.crosstrade.io/ws/stream"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Test WS starten...")

    async with websockets.connect(uri, additional_headers=headers) as ws:
        await ws.send(json.dumps({"action": "subscribe", "instruments": ["MES JUN26"]}))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Subscribe verstuurd – wacht op data...")

        async for message in ws:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] RAW → {message}")

asyncio.run(test())