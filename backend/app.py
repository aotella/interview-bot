"""Local-only HTTP surface over session_engine. Every route is a thin
wrapper - no business logic lives here, it all stays in session_engine.py
so the CLI dev scripts and this API can never drift apart.
"""

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import session_engine
from backend.question_sourcing import QuestionSourcingError
from backend.session_engine import SessionEngineError

app = FastAPI(title="Interview Prep Agent")

# Local-only tool: CORS is scoped to the Vite dev server origin, never a
# wildcard, even though the server itself only binds to 127.0.0.1.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(SessionEngineError)
def _handle_session_engine_error(request, exc: SessionEngineError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(QuestionSourcingError)
def _handle_question_sourcing_error(request, exc: QuestionSourcingError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"detail": str(exc)})


class StartSessionRequest(BaseModel):
    round_type: Literal["hld", "lld_deepdive"]


class CheckpointRequest(BaseModel):
    text: str
    input_mode: Literal["typed", "voice"]


class DiagramRequest(BaseModel):
    checkpoint_id: str
    volunteered: bool = True


@app.post("/sessions")
def start_session(req: StartSessionRequest) -> dict:
    return session_engine.start_session(req.round_type)


@app.post("/sessions/{session_id}/checkpoints")
def save_checkpoint(session_id: str, req: CheckpointRequest) -> dict:
    return session_engine.save_checkpoint(session_id, req.text, req.input_mode)


@app.post("/sessions/{session_id}/diagram")
def attach_diagram(session_id: str, req: DiagramRequest) -> dict:
    return session_engine.attach_diagram(session_id, req.checkpoint_id, req.volunteered)


@app.post("/sessions/{session_id}/pause")
def pause(session_id: str) -> dict:
    return session_engine.pause(session_id)


@app.post("/sessions/{session_id}/resume")
def resume(session_id: str) -> dict:
    return session_engine.resume(session_id)


@app.post("/sessions/{session_id}/end")
def end_session(session_id: str) -> dict:
    return session_engine.end_session(session_id)


@app.get("/sessions")
def list_sessions() -> list[dict]:
    return session_engine.list_sessions()


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        return session_engine.get_session_summary(session_id)
    except SessionEngineError as e:
        raise HTTPException(status_code=404, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
