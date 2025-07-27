import logging
import os
import sys
import tempfile
from datetime import datetime

import whisper
from services.pdf_service import get_pdf_conversation
from utils.crud import (get_all_user_personas,
                                   get_messages_from_conversation,
                                   get_persona_by_conversation_id,
                                   get_persona_by_id,
                                   insert_persona_and_conversation,
                                   save_message)
from utils.crud import \
    update_persona_description as db_update_persona_description
from models.models import Personas, SenderType, User
from core.database import create_db_and_tables
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from huggingface_hub import login
from services.Neeko.embd_roles import embed_character
from services.Neeko.infer import ask_character, load_model
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from core.auth import (auth_backend, current_active_user, fastapi_users,
                   google_oauth_client)

from services.whisper_service import transcribe_audio_file

from schemas.api_schemas import (
    UserPersonaData,
    UserMessage,
    ConversationHistory,
    UpdatePersonaDescriptionRequest,
    NewPersonaData
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(__file__)))
# Otherwise app.py doesn't see db module
sys.path.append(os.path.join(os.path.dirname(__file__)))


hf_token = os.getenv('hf_token')
login(token=hf_token)


load_dotenv('./env/.env')

# Models loading
whisper_model = None
whisper_speech = None
neeko_model = None
neeko_tokenizer = None
logging.info("Loading AI models")
try:
    whisper_model = whisper.load_model("small")
    logging.info("Whisper model loaded.")
except Exception as e:
    logging.error(f"Failed to load Whisper model: {e}")

try:
    neeko_tokenizer, neeko_model = load_model(
        lora_path="./Neeko/data/train_output")
    logging.info("Neeko model loaded.")
except Exception as e:
    logging.error(f"Failed to load Neeko model: {e}")


router = APIRouter()


@router.post('/api/get_user_personas')
async def get_user_personas(user: User = Depends(current_active_user)):
    """
    Get all personas of the user
    """
    user_id = user.id
    persona_names = await get_all_user_personas(user_id)
    return {
        'persona_names': persona_names,
    }


@router.post('/api/add_persona')
async def add_persona(request: UserPersonaData,
                      user: User = Depends(current_active_user)):
    user_id = user.id
    persona_id, conversation_id = await insert_persona_and_conversation(user_id, request.persona_name,
                                                                        request.persona_description)
    return {
        'persona_id': persona_id,
        'persona_name': request.persona_name,
        'user_id': user_id,
        'conversation_id': conversation_id,
    }


@router.post('/api/new_persona')
async def add_new_persona(
        request: NewPersonaData,
        user: User = Depends(current_active_user)):
    user_id = user.id
    user_email = user.email
    with open(f"{'./Neeko/data/seed_data/profiles'}/wiki_{request.persona_name}.txt", "w") as f:
        f.write(f"# {request.persona_name}\n\n{request.persona_description}\n")

    embed_character(
        character_name=request.persona_name,
        encoder_path="google-bert/bert-large-uncased",
        seed_data_path="./Neeko/data/seed_data",
        save_path="./Neeko/data/embed")
    persona_id, conversation_id = await insert_persona_and_conversation(user_id, request.persona_name,
                                                                        request.persona_description)
    return {
        'persona_id': persona_id,
        'persona_name': request.persona_name,
        'user_id': user_id,
        'conversation_id': conversation_id,
    }


@router.post('/api/chat_history')
async def get_chats_history(
        request: ConversationHistory,
        user: User = Depends(current_active_user)):
    """
    Get ONE specific conversation to load into the chat window.
    """
    messages = await get_messages_from_conversation(request.conversation_id)

    return {
        'messages': messages,
    }


@router.post('/api/user_message')
async def send_user_message(request: UserMessage,
                            user: User = Depends(current_active_user)):
    # Extract user ID from token
    # token = authorization.replace("Bearer ", "") if authorization else None
    # if not token:
    #     raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = user.id
    user_email = user.email
    return {
        'prompt': request.prompt,
        'response': 'I got your message',
        'user_id': user_id,
        'user_email': user_email,
    }


@router.post('/api/get_answer')
async def get_answer(
        request: UserMessage,
        User: User = Depends(current_active_user)):
    await save_message(request.conversation_id, SenderType.USER, request.prompt)

    # Retrieve actual semantic context messages as a string
    # semantic_context = await
    # retrieve_semantic_context(request.conversation_id, request.prompt)

    context_prefix = (
        "Below are a few relevant past messages from the conversation history. "
        "These should be taken into account when generating the response:\n\n")

    # Compose the prompt by merging context + user's prompt
    prompt_with_context = context_prefix + "\n\nUser's question:\n" + \
        request.prompt  # + semantic_context

    generated_text = ask_character(
        model=neeko_model,
        tokenizer=neeko_tokenizer,
        character=request.persona,
        profile_dir="./Neeko/data/seed_data/profiles",
        embed_dir="./Neeko/data/embed",
        question=prompt_with_context,
        temperature=request.temperature)

    await save_message(request.conversation_id, SenderType.BOT, generated_text)

    # await save_message_to_qdrant(request.conversation_id,
    # UserMessage.prompt, generated_text)

    return generated_text


@router.post('/api/pdf_conversation')
async def pdf_conversation(
        request: ConversationHistory,
        user: User = Depends(current_active_user)):
    """
    Get ONE specific conversation to load into the chat window.
    """
    persona: Personas = await get_persona_by_conversation_id(request.conversation_id)
    metadata = {
        "date": datetime.now(),
        "username": user.email,
        "bot_name": persona.name,
    }
    messages = await get_messages_from_conversation(request.conversation_id)
    pdf = get_pdf_conversation(metadata, messages)
    filename = f"conversation_with_{persona.name}.pdf"
    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename={0}".format(filename)},
    )


@router.get('/api/get_persona_description/{persona_id}')
async def get_persona_description(
        persona_id: int,
        user: User = Depends(current_active_user)):
    persona = await get_persona_by_id(persona_id)
    if not persona or persona.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this persona")
    return {"description": persona.description}


@router.post('/api/update_persona_description')
async def update_persona_description(
        request: UpdatePersonaDescriptionRequest,
        user: User = Depends(current_active_user)):
    persona = await get_persona_by_id(request.persona_id)
    if not persona or persona.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this persona")
    await db_update_persona_description(request.persona_id, request.new_description)
    wiki_file_path = f"./Neeko/data/seed_data/profiles/wiki_{request.persona_id}.txt"
    with open(wiki_file_path, "w") as f:
        f.write(f"# {persona.name}\n\n{request.new_description}\n")
    embed_character(
        character_name=str(
            request.persona_id),
        encoder_path="google-bert/bert-large-uncased",
        seed_data_path="./Neeko/data/seed_data",
        save_path="./Neeko/data/embed")
    return {"message": "Persona description updated successfully"}


def allowed_file(filename):
    allowed_extensions = {"mp3", "m4a"}
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in allowed_extensions


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only mp3 and m4a are allowed.")

    with tempfile.NamedTemporaryFile(delete=False, suffix='.' + file.filename.rsplit('.', 1)[1]) as temp_file:
        temp_file.write(await file.read())
        temp_file_path = temp_file.name

    try:
        result = transcribe_audio_file(
            whisper_model, temp_file_path)
        return {
            "text": result["text"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.post('/api/upload_persona_image')
async def upload_persona_image(
        persona_name: str = Form(...),
        file: UploadFile = File(...),
        user: User = Depends(current_active_user)
):
    """
    Upload and save persona image
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400, detail="File must be an image")

        # Check if it's PNG (if you want to enforce PNG only)
        if file.content_type != 'image/png':
            raise HTTPException(
                status_code=400, detail="Only PNG images are allowed")

        # Validate file size (e.g., max 5MB)
        file_size = 0
        content = await file.read()
        file_size = len(content)

        if file_size > 8 * 1024 * 1024:  # 5MB limit
            raise HTTPException(
                status_code=400, detail="File size too large (max 8MB)")

        # Create personas directory if it doesn't exist
        PERSONAS_DIR = "./personas"
        os.makedirs(PERSONAS_DIR, exist_ok=True)

        # Define the file path
        file_path = os.path.join(PERSONAS_DIR, f"{persona_name.lower()}.png")

        # Save the file
        with open(file_path, "wb") as f:
            f.write(content)

        logging.info(
            f"Persona image uploaded for {persona_name} by user {user.email}")

        return {
            "message": f"Image uploaded successfully for {persona_name}",
            "filename": f"{persona_name.lower()}.png",
            "size": file_size
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.error(f"Error uploading persona image for {persona_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image")


@router.get("/static/personas/{filename}")
async def get_persona_image(filename: str):
    file_path = f"backend/personas/{filename}"
    if os.path.exists(file_path):
        return FileResponse(
            file_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Image not found")
