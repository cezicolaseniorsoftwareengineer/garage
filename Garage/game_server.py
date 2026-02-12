import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

app = FastAPI(title="404 Garage Backend", version="1.0.0")

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS to allow Browser Game to talk to Server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# models
class ScoreEntry(BaseModel):
    player_name: str
    credits: int
    rank: str  # "Principal", "Senior", etc.
    year: str  # "2026", "1994", etc.
    ending: str # "startup", "bigtech", "dropout"
    timestamp: Optional[str] = None

# persistence
DB_FILE = "leaderboard.json"

def load_scores() -> List[dict]:
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_scores(scores: List[dict]):
    with open(DB_FILE, "w") as f:
        json.dump(scores, f, indent=2)

# routes

@app.get("/")
def serve_game():
    return FileResponse("index.html")

@app.get("/health")
def health_check():
    return {"status": "online", "system": "404 Garage API"}

@app.get("/leaderboard")
def get_leaderboard(limit: int = 10):
    scores = load_scores()
    # Sort by Credits Descending
    scores.sort(key=lambda x: x["credits"], reverse=True)
    return scores[:limit]

@app.post("/submit")
def submit_score(entry: ScoreEntry):
    scores = load_scores()

    new_record = entry.dict()
    new_record["timestamp"] = datetime.now().isoformat()

    scores.append(new_record)
    save_scores(scores)

    return {"message": "Score recorded", "rank_position": len(scores)}

if __name__ == "__main__":
    import uvicorn
    # Hot Reload enabled for dev
    uvicorn.run("game_server:app", host="0.0.0.0", port=8000, reload=True)
