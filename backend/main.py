import os
import sys

import logging
import tempfile

from starlette.exceptions import HTTPException
from starlette.responses import FileResponse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Neeko.embd_roles import embed_character
from Neeko.infer import load_model, ask_character
from fastapi.responses import StreamingResponse

# sys.path.append(os.path.join(os.path.dirname(__file__), '../security'))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(__file__)))

from fastapi import Depends, UploadFile, File, BackgroundTasks

from backend.db import User, SenderType, Personas

from huggingface_hub import login
from pydantic import BaseModel
from backend.app import app
from backend.users import current_active_user
from backend.qdrant_interactions import *
from backend.voice_communication import *
import uuid
import uvicorn
import whisper

from backend.database_interactions import (
    insert_persona_and_conversation,
    save_message,
    get_messages_from_conversation,
    get_all_user_personas,
    get_persona_by_conversation_id
)

from conversation_pdf import get_pdf_conversation

load_dotenv('./env/.env')

# login to HF
# you should place the HugginFace token in the .env
# hf_token=<hf_token>
hf_token = os.getenv('hf_token')
login(token=hf_token)

# app = FastAPI()

##### Models loading
whisper_model = None
whisper_speech = None
neeko_model = None
neeko_tokenizer = None
logging.info("Loading AI models")
try:
    whisper_model = whisper.load_model("base")
    logging.info("Whisper model loaded.")
except Exception as e:
    logging.error(f"Failed to load Whisper model: {e}")

try:
    neeko_tokenizer, neeko_model = load_model(lora_path="../Neeko/data/train_output")
    logging.info("Neeko model loaded.")
except Exception as e:
    logging.error(f"Failed to load Neeko model: {e}")

try:
    from whisperspeech.pipeline import Pipeline
    whisper_speech = Pipeline(t2s_ref='whisperspeech/whisperspeech:t2s-v1.95-small-8lang.model',
                s2a_ref='whisperspeech/whisperspeech:s2a-v1.95-medium-7lang.model')
    logging.info("WhisperSpeech model loaded.")
except Exception as e:
    logging.error(f"Failed to load WhisperSpeech model: {e}")


class UserMessage(BaseModel):
    prompt: str
    persona: str
    conversation_id: int


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


@app.post('/api/get_user_personas')
async def get_user_personas(user: User = Depends(current_active_user)):
    """
    Get all personas of the user
    """
    user_id = user.id
    persona_names = await get_all_user_personas(user_id)
    return {
        'persona_names': persona_names,
    }


@app.post('/api/add_persona')
async def add_persona(request: UserPersonaData, user: User = Depends(current_active_user)):
    user_id = user.id
    persona_id, conversation_id = await insert_persona_and_conversation(user_id, request.persona_name,
                                                                        request.persona_description)
    return {
        'persona_id': persona_id,
        'persona_name': request.persona_name,
        'user_id': user_id,
        'conversation_id': conversation_id,
    }


@app.post('/api/new_persona')
async def add_new_persona(request: NewPersonaData, user: User = Depends(current_active_user)):
    user_id = user.id
    user_email = user.email
    with open(f"{'../Neeko/data/seed_data/profiles'}/wiki_{request.persona_name}.txt", "w") as f:
        f.write(f"# {request.persona_name}\n\n{request.persona_description}\n")

    embed_character(character_name=request.persona_name, encoder_path="google-bert/bert-large-uncased",
                    seed_data_path="../Neeko/data/seed_data",
                    save_path="../Neeko/data/embed")
    persona_id, conversation_id = await insert_persona_and_conversation(user_id, request.persona_name,
                                                                        request.persona_description)
    return {
        'persona_id': persona_id,
        'persona_name': request.persona_name,
        'user_id': user_id,
        'conversation_id': conversation_id,
    }


@app.post('/api/chat_history')
async def get_chats_history(request: ConversationHistory, user: User = Depends(current_active_user)):
    """
    Get ONE specific conversation to load into the chat window.
    """
    messages = await get_messages_from_conversation(request.conversation_id)

    return {
        'messages': messages,
    }


@app.post('/api/user_message')
async def send_user_message(request: UserMessage, user: User = Depends(current_active_user)):
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


@app.post('/api/get_answer')
async def get_answer(request: UserMessage, User: User = Depends(current_active_user)):
    await save_message(request.conversation_id, SenderType.USER, request.prompt)

    # Search in qdrant before generating message
    # search_results = search_messages_in_qdrant(request.conversation_id)

    # Prepare message from qdrant
    # conversation_history = process_qdrant_results(search_results)

    generated_text = ask_character(model=neeko_model, tokenizer=neeko_tokenizer, character=request.persona,
                                   profile_dir="../Neeko/data/seed_data/profiles", embed_dir="../Neeko/data/embed",
                                   question=request.prompt)

    # Generate the vector (embedding) for the generated text (use model's embedding layer)
    # inputs_for_vector = neeko_tokenizer(generated_text, return_tensors="pt")
    # vector = neeko_model.encode(inputs_for_vector['input_ids']).detach().numpy().flatten()  # Generate the embedding
    # vector = vector.tolist()  # Convert to list to save to Qdrant

    # Save the generated message (or raw token output if desired) to Qdrant
    # save_message_to_qdrant(request.conversation_id, SenderType.BOT, generated_text, vector)

    await save_message(request.conversation_id, SenderType.BOT, generated_text)
    return generated_text


@app.post('/api/pdf_conversation')
async def pdf_conversation(request: ConversationHistory, user: User = Depends(current_active_user)):
    """
    Get ONE specific conversation to load into the chat window.
    """
    persona: Personas = await get_persona_by_conversation_id(request.conversation_id)
    metadata = {
        "date": "TODO",
        "username": User.email,
        "bot_name": persona.name,
    }
    messages = await get_messages_from_conversation(request.conversation_id)
    pdf = get_pdf_conversation(metadata, messages)
    filename = f"conversation_with_{persona.name}.pdf"
    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename={0}".format(filename)},
    )



def allowed_file(filename):
    allowed_extensions = {"mp3", "m4a"}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only mp3 and m4a are allowed.")

    with tempfile.NamedTemporaryFile(delete=False, suffix='.' + file.filename.rsplit('.', 1)[1]) as temp_file:
        temp_file.write(await file.read())
        temp_file_path = temp_file.name

    try:
        result = transcribe_audio_file(whisper_model, temp_file_path)
        return {
            "text": result["text"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

class TextToSpeech(BaseModel):
    text: str
    lang: str = 'en'
@app.post("/text_to_speech")
async def text_to_speech(request: TextToSpeech, background_tasks: BackgroundTasks):
    # Generate a unique filename
    output_filename = f"output_{uuid.uuid4().hex}.wav"

    # Generate speech and save to file
    whisper_speech.generate_to_file(
        text=request.text,
        lang=request.lang,
        fname=output_filename
    )

    background_tasks.add_task(os.remove, output_filename)

    return FileResponse(output_filename, media_type="audio/wav", filename=output_filename)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, ssl_keyfile="env/key.pem", ssl_certfile="env/cert.pem")
    print(app.routes)
