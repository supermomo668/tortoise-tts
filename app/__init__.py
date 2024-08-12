# app/__init__.py
from fastapi import FastAPI
from app.lifespan import lifespan
from app.routes import register_routes

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    register_routes(app)
    return app