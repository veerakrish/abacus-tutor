import os
import json
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from tutor_engine import explain_addition
from curriculum import generate_levels
from ai_tutor import generate_explanation

# Load environment variables from .env file
load_dotenv(dotenv_path="../.env")

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small-latest"

DEFAULT_SYSTEM_PROMPT = (
    "You are Professor Abby, a cheerful AI abacus tutor for children aged 6-12.\n"
    "Rules: Use VERY simple words. Keep responses 2-4 sentences MAX. Use fun emojis heavily.\n"
    "You know the 17-rod soroban abacus deeply:\n"
    "- Heaven beads (top, 1 per rod) = value 5 each\n"
    "- Earth beads (bottom, 4 per rod) = value 1 each\n"
    "- Rods right-to-left: ones, tens, hundreds, thousands...\n"
    "- Addition = push beads toward center bar\n"
    "- Subtraction = pull beads away from center bar\n"
    "- Multiplication = repeated addition\n"
    "- Division = repeated subtraction\n"
    "Always encourage kids! Be super positive and excited! Never give long explanations."
)

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    system: Optional[str] = None
    max_tokens: int = 300


class TTSRequest(BaseModel):
    text: str
    lang: str = "en-US"  # BCP-47, e.g. en-US, te-IN, hi-IN, ta-IN, es-ES
    slow: bool = False


# BCP-47 -> gTTS lang map. gTTS uses short codes (with a few exceptions like zh-CN).
_GTTS_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "te": "te",
    "ta": "ta",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "ja": "ja",
    "zh": "zh-CN",
    "ar": "ar",
}


def _build_payload(req: ChatRequest, stream: bool) -> dict:
    sys_prompt = req.system or DEFAULT_SYSTEM_PROMPT
    msgs = [{"role": "system", "content": sys_prompt}]
    msgs.extend([m.dict() for m in req.messages])
    return {
        "model": MISTRAL_MODEL,
        "max_tokens": req.max_tokens,
        "messages": msgs,
        "stream": stream,
    }


@app.get("/")
async def serve_home():
    # This sends the HTML file to the browser
    return FileResponse("abacus-tutor-ai.html")


@app.get("/levels")
def levels():
    return generate_levels()


@app.get("/add")
def add(a: int, b: int):
    explanation = generate_explanation(a, b)
    logic = explain_addition(a, b)

    return {
        "steps": explanation["telugu"],
        "english_steps": explanation["english"],
        "actions": logic["actions"],
        "result": logic["result"]
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    """Non-streaming chat proxy to Mistral."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = _build_payload(req, stream=False)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(MISTRAL_API_URL, headers=headers, json=payload)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        data = r.json()

    text = ""
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        text = ""
    return {"text": text}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming (SSE) chat proxy to Mistral."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY not set")

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {api_key}",
    }
    payload = _build_payload(req, stream=True)

    async def event_generator():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", MISTRAL_API_URL, headers=headers, json=payload
            ) as r:
                if r.status_code != 200:
                    err = await r.aread()
                    yield f"data: {json.dumps({'error': err.decode('utf-8', 'ignore')})}\n\n"
                    return
                async for line in r.aiter_lines():
                    if line:
                        # Forward Mistral's SSE lines unchanged
                        yield line + "\n"
                    else:
                        yield "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/tts")
def tts(req: TTSRequest):
    """Server-side text-to-speech using gTTS.

    Used for languages browsers usually can't speak locally (Telugu, Tamil, Hindi, ...).
    Returns an MP3 binary the frontend plays via an <audio> element.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    try:
        from gtts import gTTS  # lazy import so backend still boots without gTTS installed
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="gTTS not installed. Run: pip install gtts",
        )

    short = req.lang.split("-")[0].lower() if req.lang else "en"
    code = _GTTS_LANG_MAP.get(short, "en")

    # gTTS has per-request length limits; chunk very long inputs by sentence.
    try:
        from io import BytesIO
        buf = BytesIO()
        gTTS(text=text, lang=code, slow=req.slow).write_to_fp(buf)
        audio = buf.getvalue()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-TTS-Lang": code},
    )
