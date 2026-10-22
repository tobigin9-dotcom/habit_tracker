from fastapi import FastAPI

from app.routes import router

app = FastAPI(
    title="Habit Tracker API",
    version="1.0.0",
    description="Private habit tracking API for the Telegram bot.",
)
app.include_router(router)


@app.get("/health", tags=["system"])
async def health_check():
    """Return service health status."""
    return {"status": "ok"}
