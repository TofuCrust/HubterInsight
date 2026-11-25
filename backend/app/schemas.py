from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    # ID acak dari browser untuk mengelompokkan percakapan di log evaluasi. Bukan identitas.
    session_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class FeedbackRequest(BaseModel):
    chat_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    rating: Literal[-1, 1] | None = None
    comment: str | None = Field(default=None, max_length=2000)


class Source(BaseModel):
    id: int
    title: str
    location: str | None = None
    snippet: str
    # Teks lengkap potongan untuk model. Tidak ikut dikirim ke browser (exclude=True).
    context: str | None = Field(default=None, exclude=True)
