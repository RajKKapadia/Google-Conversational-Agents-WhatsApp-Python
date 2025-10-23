if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(
        app="src.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8080")),
        reload=True,
    )
