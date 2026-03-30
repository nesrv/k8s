from fastapi import FastAPI

app = FastAPI(title="Docker Desktop K8s Lab v1.1")


@app.get("/")
def root():
    return {"msg": "hello from docker-desktop k8s v1.1"}


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/crash")
def crash():
    import os
    os._exit(1)
