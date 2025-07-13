# server_ws.py
import asyncio
import websockets

async def handler(websocket, path):
    print("Cliente WebSocket conectado!")
    async for message in websocket:
        print(f"Mensagem recebida: {message}")
        await websocket.send("ACK: " + message)  # Confirmação de recebimento

start_server = websockets.serve(handler, "localhost", 5000)

try:
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    print("Servidor WebSocket encerrado")
