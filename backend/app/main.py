from fastapi import FastAPI

app = FastAPI(title="Meeting Notes AI")


@app.get("/")
def read_root():
    return {"message": "Meeting Notes AI backend is running"}
