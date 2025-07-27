from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.models import Conversations, Personas, Messages
from core.database import engine


# Async version for async contexts
async def insert_persona_and_conversation(user_id, pers_name, descr):
    async with AsyncSession(engine) as session:
        persona = await get_persona(user_id, pers_name, descr, session)
        conversation = await get_conversation(user_id, persona.id, session)
        return persona.id, conversation.id


async def get_persona(user_id, pers_name, descr, session):
    async with session:
        # Check if the persona already exists
        query = select(Personas).filter_by(user_id=user_id, name=pers_name)
        result = await session.execute(query)
        existing_persona = result.scalars().first()
        print(existing_persona is not None, existing_persona, user_id, pers_name, descr)
        if existing_persona:
            return existing_persona

        # If not found, create new persona
        new_persona = Personas(user_id=user_id, name=pers_name, description=descr)
        session.add(new_persona)
        await session.commit()
        await session.refresh(new_persona)
        return new_persona


async def get_conversation(user_id, persona_id, session):
    async with session:
        # Check if conversation with corresponding user_id and persona_id already exists
        query = select(Conversations).filter_by(user_id=user_id, persona_id=persona_id)
        result = await session.execute(query)
        existing_conversation = result.scalars().first()
        print(existing_conversation is not None, existing_conversation, user_id, persona_id)
        if existing_conversation:
            return existing_conversation
        # If not found, create new conversation
        new_conversation = Conversations(user_id=user_id, persona_id=persona_id)
        session.add(new_conversation)
        await session.commit()
        await session.refresh(new_conversation)
        return new_conversation


async def save_message(conversation_id, sender, content):
    async with AsyncSession(engine) as session:
        new_message = Messages(conversation_id=conversation_id, sender=sender, content=content)
        session.add(new_message)
        await session.commit()
        await session.refresh(new_message)
        return new_message


async def get_messages_from_conversation(conversation_id):
    async with AsyncSession(engine) as session:
        query = select(Messages).filter_by(conversation_id=conversation_id).order_by(Messages.sent_at)
        result = await session.execute(query)
        messages = result.scalars().all()
        return [{"text": msg.content, "sender": msg.sender} for msg in messages]


async def get_all_user_personas(user_id):
    async with AsyncSession(engine) as session:
        query = select(Personas).filter_by(user_id=user_id)
        result = await session.execute(query)
        personas = result.scalars().all()
        return [{"persona_name": persona.name} for persona in personas]


async def get_persona_by_conversation_id(conversation_id):
    async with AsyncSession(engine) as session:
        query = select(Personas).join(Conversations).filter(Conversations.id == conversation_id)
        result = await session.execute(query)
        persona = result.scalars().first()
        return persona


async def get_persona_by_id(persona_id: int):
    async with AsyncSession(engine) as session:
        persona = await session.get(Personas, persona_id)
        return persona


async def update_persona_description(persona_id: int, new_description: str):
    async with AsyncSession(engine) as session:
        persona = await session.get(Personas, persona_id)
        if persona:
            persona.description = new_description
            await session.commit()