from typing import Optional
from sqlmodel import SQLModel, Field

class ChatRoom(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)

class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    room_id: int = Field(foreign_key="chatroom.id")

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="chatroom.id")
    participant_name: str
    content: str
    sent_at: Optional[str] = Field(default=None)
