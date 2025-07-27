import uuid

from pydantic import BaseModel


class UserMessage(BaseModel):
    prompt: str
    persona: str
    conversation_id: int
    temperature: float


class UserPersonaData(BaseModel):
    persona_name: str
    persona_description: str


class ConversationHistory(BaseModel):
    conversation_id: int


class NewPersonaData(BaseModel):
    persona_name: str
    persona_description: str


class UserData(BaseModel):
    user_id: uuid.UUID


class UpdatePersonaDescriptionRequest(BaseModel):
    persona_id: int
    new_description: str