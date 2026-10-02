from fastapi import FastAPI

app = FastAPI(title="Webhook Gateway API")


@app.get("/health_check")
def health_check():
    return {"status": "ok"}