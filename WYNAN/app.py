from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from metrics_engine import build_symbol_tables, get_available_symbols

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="WYNAN Market Microstructure Dashboard")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/symbols")
def list_symbols():
    symbols = get_available_symbols()
    return {"symbols": symbols}


@app.get("/api/dashboard/{symbol}")
def get_symbol_dashboard(symbol: str):
    available = get_available_symbols()
    symbol_upper = symbol.upper()
    if symbol_upper not in available:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol_upper} not found in binance_aggts_hist/")

    data = build_symbol_tables(symbol_upper)
    data["updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return data