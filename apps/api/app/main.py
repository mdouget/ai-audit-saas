from fastapi import FastAPI
from pydantic import BaseModel, Field
from .scoring import Answer, calculate, Status

app = FastAPI(title="AI Assurance API", version="0.1.0")

class ResponseItem(BaseModel):
    domain: str
    status: Status
    weight: float = Field(default=1, gt=0)

class ScoreRequest(BaseModel):
    responses: list[ResponseItem]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/v1/demo/score")
def demo_score(payload: ScoreRequest):
    """Synthetic/demo-only endpoint; no customer storage or tenant identity."""
    return calculate([Answer(**r.model_dump()) for r in payload.responses])
