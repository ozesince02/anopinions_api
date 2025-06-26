# app/main.py
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import init_db, get_session, async_session
from .models import ChatRoom, Participant, Message

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(room, []).append(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        self.active[room].remove(websocket)

    async def broadcast(self, room: str, msg: dict):
        for sock in list(self.active.get(room, [])):
            await sock.send_json(msg)

manager = ConnectionManager()

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.post("/rooms/")
async def create_room(session: AsyncSession = Depends(get_session)):
    code = uuid.uuid4().hex[:8]
    room = ChatRoom(code=code)
    session.add(room)
    await session.commit()
    return {"code": code}

@app.get("/rooms/{code}/history")
async def get_history(code: str, session: AsyncSession = Depends(get_session)):
    room = (await session.exec(
        select(ChatRoom).where(ChatRoom.code == code)
    )).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    msgs = (await session.exec(
        select(Message)
        .where(Message.room_id == room.id)
        .order_by(Message.sent_at)
    )).all()
    return msgs

@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str, name: str | None = None):
    # 1) Verify room & assign/reuse name in a session
    async with async_session() as session:
        room = (await session.exec(
            select(ChatRoom).where(ChatRoom.code == code)
        )).first()
        if not room:
            await websocket.close(code=1008)
            return

        if not name:
            cnt = (await session.exec(
                select(Participant).where(Participant.room_id == room.id)
            )).count()
            name = f"Badmos {cnt+1}"
            session.add(Participant(name=name, room_id=room.id))
            await session.commit()

    # 2) Accept & track connection
    await manager.connect(code, websocket)

    # 3) Send your identity
    await websocket.send_json({"type": "your_identity", "name": name})

    # 4) Send chat history (reuse the REST function)
    history = await get_history(code)
    await websocket.send_json({"type": "history", "msgs": history})

    # 5) Broadcast join notice
    await manager.broadcast(code, {
        "type": "message",
        "system": True,
        "text": f"{name} joined."
    })

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "chat_message":
                content = data["content"]
                # persist message
                async with async_session() as session:
                    msg = Message(
                        room_id=room.id,
                        participant_name=name,
                        content=content
                    )
                    session.add(msg)
                    await session.commit()
                # broadcast to all
                await manager.broadcast(code, {
                    "type": "message",
                    "system": False,
                    "name": name,
                    "text": content
                })
    except WebSocketDisconnect:
        manager.disconnect(code, websocket)
        await manager.broadcast(code, {
            "type": "message",
            "system": True,
            "text": f"{name} left."
        })
