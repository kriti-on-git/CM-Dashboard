from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

@app.get("/")
def root():
    return {"message": "Welcome to Crisis Twin AI API"}

# Example of including an API router
# from app.api.routes import users
# app.include_router(users.router, prefix=settings.API_V1_STR + "/users", tags=["users"])
