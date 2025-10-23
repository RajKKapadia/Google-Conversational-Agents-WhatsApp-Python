from fastapi import FastAPI

from src import logging

app = FastAPI(title="CA WhatsApp Integration")


logger = logging.getLogger(__name__)


@app.get("/webhook", response_model=None)
async def handle_get_webhook():
    pass


@app.post("/webhook", response_model=None)
async def handle_post_webhook():
    pass
