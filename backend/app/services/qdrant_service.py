import asyncio
import os
import uuid
from datetime import datetime
from typing import Dict

import numpy as np
import torch
# from torch_geometric.nn.nlp import SentenceTransformer
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.grpc import SearchParams
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, SearchParams
from qdrant_client.models import PointStruct
from transformers import AutoTokenizer, AutoModel

load_dotenv('./env/.env')

qdrant_client = QdrantClient(
    url="https://91dcb42b-7324-423c-9272-a469314e87b0.europe-west3-0.gcp.cloud.qdrant.io:6333",
    api_key=os.getenv("qdrant_key"),

)

COLLECTION_NAME = "conversation_messages"

print(qdrant_client.get_collections())

#create collection
#
# qdrant_client.recreate_collection(
#     collection_name=COLLECTION_NAME,
#     vectors_config=VectorParams(size=768, distance=Distance.COSINE),
# )


tokenizer = AutoTokenizer.from_pretrained("bert-base-multilingual-cased")
model = AutoModel.from_pretrained("bert-base-multilingual-cased")

print("BBBB")

async def get_embeddings(text: str) -> list:
    """Generate embeddings for the input text using DistilBERT model."""
    print("generating_embed")
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().tolist()
    return embeddings


print(qdrant_client.get_collections())


async def save_message_to_qdrant(conversation_id, user_message, response):
    # Combine prompt and response into a single string
    combined_text = f"User: {user_message}\nBot: {response}"

    # Generate embedding vector
    embedding_vector = await get_embeddings(combined_text)

    # Metadata for retrieval
    metadata: Dict = {
        "conversation_id": conversation_id,
        "user_prompt": user_message,
        "bot_response": response,
        "timestamp": datetime.utcnow()
    }

    # Save to Qdrant
    point = PointStruct(
        id=str(uuid.uuid4()),  # string UUID
        vector=embedding_vector,
        payload=metadata
    )

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[point]
    ))


## This retrieves history by conversation-id as-is. No search by context, ordered by timestamps
async def retrieve_history(conversation_id):
    # Use a zero vector of correct size (e.g., 768, adjust to your model)
    dummy_vector = np.zeros(768).tolist()

    # Define filter for conversation_id
    search_filter = Filter(
        must=[
            FieldCondition(
                key="conversation_id",
                match=MatchValue(value=conversation_id)
            )
        ]
    )

    def qdrant_search():
        return qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=dummy_vector,
            limit=100,
            query_filter=search_filter,
            search_params=SearchParams(hnsw_ef=128, exact=True)  # exact filter search
        )

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, qdrant_search)

    # results is a list of ScoredPoint objects
    points = results

    # Sort by timestamp (assuming ISO8601 string)
    points_sorted = sorted(
        points,
        key=lambda p: datetime.fromisoformat(p.payload.get("timestamp")),
        reverse=False
    )

    last_20 = points_sorted[-20:]

    messages = []
    for p in last_20:
        user_prompt = p.payload.get("user_prompt", "")
        bot_response = p.payload.get("bot_response", "")
        timestamp = p.payload.get("timestamp", "")
        messages.append(f"[{timestamp}] User: {user_prompt}\n[{timestamp}] Bot: {bot_response}")

    context = "\n\n".join(messages)
    return context


## This retrieves history with extra semantic search. Returns messages in order depending of message relevance.
async def retrieve_semantic_context(conversation_id, user_query):
    # Step 1: Embed the user query into a vector
    query_vector = await get_embeddings(user_query)  # your embedding function, returns e.g. 768-d vector

    # Step 2: Define the same conversation_id filter
    search_filter = Filter(
        must=[
            FieldCondition(
                key="conversation_id",
                match=MatchValue(value=conversation_id)
            )
        ]
    )

    def qdrant_search():
        return qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=5,
            query_filter=search_filter,
            search_params=SearchParams(hnsw_ef=128)
        )

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, qdrant_search)

    # Sort by relevance score or timestamp if you want
    points = results

    # Format the context for LLaMA
    messages = []
    for p in points:
        user_prompt = p.payload.get("user_prompt", "")
        bot_response = p.payload.get("bot_response", "")
        timestamp = p.payload.get("timestamp", "")
        messages.append(f"[{timestamp}] User: {user_prompt}\n[{timestamp}] Bot: {bot_response}")

    context = "\n\n".join(messages)
    return context


## test of saving conversation:
async def main():
    # user_msg = "A knock knock joke"
    # bot_response = "Knock, knock. Who's there? Nobel. Nobel who? Nobel...that's why I knocked."
    # await save_message_to_qdrant("123", user_msg, bot_response)
    # print("Message saved to Qdrant.")


    conversation_id = "123"
    print("Retrieve and contextualize")
    context = await retrieve_history(conversation_id)
    print(context)
    print("Retrieve semantic context")
    context = await retrieve_semantic_context(conversation_id, "jokes")
    print(context)

#
# if __name__ == "__main__":
#     asyncio.run(main())()