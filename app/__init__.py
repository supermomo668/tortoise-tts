# app/__init__.py
from fastapi import FastAPI

from app.lifespan import lifespan
from app.routes import auth, task, tts

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(auth.router)
    app.include_router(task.router)
    app.include_router(tts.router)
    # register_routes(app)
    return app