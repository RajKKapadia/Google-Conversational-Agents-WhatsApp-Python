"""
ARQ worker runner — works around Python 3.14 asyncio.get_event_loop() removal.

Usage:  uv run python run_worker.py
"""

import asyncio

from arq.worker import create_worker

from src.worker import WorkerSettings

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    worker = create_worker(WorkerSettings)
    worker.run()
