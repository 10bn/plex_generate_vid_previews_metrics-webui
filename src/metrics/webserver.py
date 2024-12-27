# src/metrics/webserver.py

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from src.metrics.db import get_latest_metrics, init_db
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

@app.on_event("startup")
def startup_event():
    """Initialize the database on startup."""
    init_db()

@app.get("/", response_class=HTMLResponse)
def read_metrics(request: Request):
    """Render the latest metrics on the homepage."""
    metrics = get_latest_metrics()
    return templates.TemplateResponse("metrics.html", {"request": request, "metrics": metrics})

def run_webserver():
    """Run the FastAPI webserver using Uvicorn."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
