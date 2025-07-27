import os
import sys
from contextlib import asynccontextmanager

from models.models import User
from core.database import create_db_and_tables
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1 import routes
from schemas.user_schemas import UserCreate, UserRead, UserUpdate
from starlette.middleware.sessions import SessionMiddleware
from core.auth import (SECRET, auth_backend, current_active_user, fastapi_users,
                   google_oauth_client)

from models import *


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not needed if you setup a migration system like Alembic
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost:5173", "https://127.0.0.1:5173", "https://aip-frontend-react:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key="supertajnyklucz"
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"]
)
auth_path = "/auth"
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix=auth_path,
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix=auth_path,
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix=auth_path,
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
app.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client,
        auth_backend,
        SECRET,
        redirect_url="https://localhost:5173/oauth/callback"
    ),
    prefix="/auth/google",
    tags=["auth"],
)
app.include_router(routes.router)

@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}!"}

import uvicorn
from core.auth import current_active_user

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ssl_keyfile="backend/env/key.pem", ssl_certfile="backend/env/cert.pem")
