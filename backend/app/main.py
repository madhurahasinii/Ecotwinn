from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import io
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parent.parent / "ecotwin.db"
app = FastAPI(title="EcoTwin API", version="0.1.0", description="Local prototype API for the EcoTwin smart lab waste bin.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS bins (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL,
          stream TEXT NOT NULL, capacity_kg REAL NOT NULL, current_kg REAL NOT NULL,
          first_deposit_at TEXT, last_seen_at TEXT NOT NULL, online INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS deposits (
          id INTEGER PRIMARY KEY AUTOINCREMENT, bin_id TEXT NOT NULL, weight_g REAL NOT NULL,
          deposited_at TEXT NOT NULL, user_name TEXT, experiment TEXT, attribution_status TEXT NOT NULL,
          event_source TEXT NOT NULL DEFAULT 'simulated'
        );
        CREATE TABLE IF NOT EXISTS alerts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, bin_id TEXT NOT NULL, severity TEXT NOT NULL,
          title TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS dispatches (
          id INTEGER PRIMARY KEY AUTOINCREMENT, bin_id TEXT NOT NULL, dispatch_kg REAL NOT NULL,
          store_scale_kg REAL, vendor_receipt_kg REAL, dispatched_at TEXT NOT NULL, note TEXT
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM bins").fetchone()[0]
        if count == 0:
            now = datetime.now(timezone.utc)
            bins = [
                ("ET-LIQ-01", "Chemistry · Liquid Station 01", "Chemistry", "Liquid chemical waste", 50.0, 18.65, (now-timedelta(days=76)).isoformat(), now.isoformat(), 1),
                ("ET-SOL-02", "Chemical Engg · Solid Bin 02", "Chemical Engineering", "Solid chemical waste", 100.0, 42.30, (now-timedelta(days=49)).isoformat(), now.isoformat(), 1),
                ("ET-LIQ-03", "Mechanical · Liquid Station 03", "Mechanical Engineering", "Liquid chemical waste", 50.0, 39.80, (now-timedelta(days=87)).isoformat(), now.isoformat(), 1),
                ("ET-SCI-04", "Science · Liquid Station 04", "Science", "Liquid chemical waste", 50.0, 6.25, None, now.isoformat(), 0),
            ]
            db.executemany("INSERT INTO bins VALUES (?,?,?,?,?,?,?,?,?)", bins)
            demo = [
                ("ET-LIQ-01", 245.0, now-timedelta(minutes=8), "A. Sharma", "Solvent recovery experiment", "Attributed"),
                ("ET-SOL-02", 520.0, now-timedelta(minutes=26), "Unassigned", "Not selected", "Needs attribution"),
                ("ET-LIQ-01", 180.0, now-timedelta(hours=2), "M. Rao", "Organic chemistry lab", "Attributed"),
                ("ET-LIQ-03", 760.0, now-timedelta(hours=5), "Unassigned", "Not selected", "Needs attribution"),
                ("ET-SOL-02", 95.0, now-timedelta(days=1), "P. Singh", "Materials lab", "Attributed"),
                ("ET-LIQ-01", 330.0, now-timedelta(days=2), "T. Das", "Teaching lab", "Attributed"),
            ]
            for bin_id, weight, at, user, experiment, status in demo:
                db.execute("INSERT INTO deposits(bin_id,weight_g,deposited_at,user_name,experiment,attribution_status,event_source) VALUES(?,?,?,?,?,?,?)",
                           (bin_id, weight, at.isoformat(), user, experiment, status, "demo seed"))
            alerts = [
                ("ET-LIQ-03", "critical", "Storage limit approaching", "First deposit was 87 days ago. Arrange pickup before day 90.", (now-timedelta(minutes=14)).isoformat(), 0),
                ("ET-LIQ-01", "warning", "Storage age warning", "First deposit was 76 days ago. Plan pickup before day 90.", (now-timedelta(hours=1)).isoformat(), 0),
                ("ET-LIQ-03", "warning", "High bin weight", "Bin is above 75% of rated capacity.", (now-timedelta(hours=3)).isoformat(), 0),
                ("ET-SCI-04", "info", "Device offline", "No recent heartbeat. Check power and campus Wi-Fi.", (now-timedelta(hours=4)).isoformat(), 0),
            ]
            db.executemany("INSERT INTO alerts(bin_id,severity,title,detail,created_at,resolved) VALUES(?,?,?,?,?,?)", alerts)
            db.execute("INSERT INTO dispatches(bin_id,dispatch_kg,store_scale_kg,vendor_receipt_kg,dispatched_at,note) VALUES(?,?,?,?,?,?)",
                       ("ET-SOL-02", 8.40, 8.37, 8.31, (now-timedelta(days=4)).isoformat(), "Demo dispatch record"))

init_db()

class SimulateDeposit(BaseModel):
    bin_id: str
    weight_g: float = Field(gt=0, le=100000)
    user_name: Optional[str] = None
    experiment: Optional[str] = None

class DispatchCreate(BaseModel):
    bin_id: str
    dispatch_kg: float = Field(gt=0)
    store_scale_kg: Optional[float] = Field(default=None, gt=0)
    vendor_receipt_kg: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = None

def rows(query, params=()):
    with connect() as db:
        return [dict(r) for r in db.execute(query, params).fetchall()]

@app.get("/health")
def health():
    return {"status": "ok", "service": "ecotwin-api", "time": now_iso()}

@app.get("/api/summary")
def summary():
    with connect() as db:
        bins = db.execute("SELECT * FROM bins").fetchall()
        deposits = db.execute("SELECT * FROM deposits").fetchall()
        alerts = db.execute("SELECT * FROM alerts WHERE resolved=0").fetchall()
        total_kg = sum(float(b["current_kg"]) for b in bins)
        cap_kg = sum(float(b["capacity_kg"]) for b in bins)
        attributed = sum(1 for d in deposits if d["attribution_status"] == "Attributed")
        total = len(deposits)
        return {
            "active_bins": sum(1 for b in bins if b["online"]),
            "total_bins": len(bins),
            "stored_kg": round(total_kg, 2),
            "capacity_percent": round((total_kg/cap_kg*100) if cap_kg else 0, 1),
            "deposits_today": sum(1 for d in deposits if d["deposited_at"][:10] == datetime.now(timezone.utc).date().isoformat()),
            "unresolved_alerts": len(alerts),
            "attribution_rate": round(attributed/total*100) if total else 0,
            "total_deposits": total,
        }

@app.get("/api/bins")
def get_bins():
    bins = rows("SELECT * FROM bins ORDER BY name")
    now = datetime.now(timezone.utc)
    for b in bins:
        age = None
        if b["first_deposit_at"]:
            try:
                age = max(0, (now - datetime.fromisoformat(b["first_deposit_at"])).days)
            except ValueError:
                age = None
        b["storage_age_days"] = age
        b["fill_percent"] = round(float(b["current_kg"])/float(b["capacity_kg"])*100, 1)
        b["online"] = bool(b["online"])
        b["days_to_limit"] = None if age is None else max(0, 90-age)
        b["status"] = "Offline" if not b["online"] else ("Pickup needed" if b["fill_percent"] >= 80 or (age is not None and age >= 85) else "Monitoring")
    return bins

@app.get("/api/deposits")
def get_deposits(bin_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(100, ge=1, le=500)):
    query = "SELECT d.*, b.name AS bin_name FROM deposits d LEFT JOIN bins b ON b.id=d.bin_id"
    clauses, params = [], []
    if bin_id:
        clauses.append("d.bin_id=?"); params.append(bin_id)
    if status:
        clauses.append("d.attribution_status=?"); params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY d.deposited_at DESC LIMIT ?"; params.append(limit)
    return rows(query, params)

@app.post("/api/deposits/simulate")
def simulate_deposit(body: SimulateDeposit):
    with connect() as db:
        bin_row = db.execute("SELECT * FROM bins WHERE id=?", (body.bin_id,)).fetchone()
        if not bin_row:
            raise HTTPException(status_code=404, detail="Bin not found")
        at = now_iso()
        status = "Attributed" if body.user_name and body.experiment else "Needs attribution"
        user_name = body.user_name or "Unassigned"
        experiment = body.experiment or "Not selected"
        db.execute("INSERT INTO deposits(bin_id,weight_g,deposited_at,user_name,experiment,attribution_status,event_source) VALUES(?,?,?,?,?,?,?)",
                   (body.bin_id, body.weight_g, at, user_name, experiment, status, "simulated dashboard event"))
        db.execute("UPDATE bins SET current_kg=MIN(capacity_kg, current_kg + ?), first_deposit_at=COALESCE(first_deposit_at, ?), last_seen_at=? WHERE id=?",
                   (body.weight_g/1000, at, at, body.bin_id))
        new_weight = float(bin_row["current_kg"]) + body.weight_g/1000
        if new_weight/float(bin_row["capacity_kg"]) >= .8:
            db.execute("INSERT INTO alerts(bin_id,severity,title,detail,created_at,resolved) VALUES(?,?,?,?,?,0)",
                       (body.bin_id, "warning", "Pickup requested", "Bin has reached at least 80% of rated capacity.", at))
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"ok": True, "id": new_id, "bin_id": body.bin_id, "weight_g": body.weight_g, "deposited_at": at, "attribution_status": status}

@app.get("/api/alerts")
def get_alerts(include_resolved: bool = False):
    query = "SELECT a.*, b.name AS bin_name FROM alerts a LEFT JOIN bins b ON b.id=a.bin_id"
    if not include_resolved:
        query += " WHERE a.resolved=0"
    query += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, created_at DESC"
    return rows(query)

@app.post("/api/dispatches")
def create_dispatch(body: DispatchCreate):
    with connect() as db:
        bin_row = db.execute("SELECT * FROM bins WHERE id=?", (body.bin_id,)).fetchone()
        if not bin_row:
            raise HTTPException(status_code=404, detail="Bin not found")
        at = now_iso()
        db.execute("INSERT INTO dispatches(bin_id,dispatch_kg,store_scale_kg,vendor_receipt_kg,dispatched_at,note) VALUES(?,?,?,?,?,?)",
                   (body.bin_id, body.dispatch_kg, body.store_scale_kg, body.vendor_receipt_kg, at, body.note))
        if body.store_scale_kg is not None and body.vendor_receipt_kg is not None:
            gap = abs(body.store_scale_kg-body.vendor_receipt_kg)/max(body.store_scale_kg, .001)*100
            if gap > 2:
                db.execute("INSERT INTO alerts(bin_id,severity,title,detail,created_at,resolved) VALUES(?,?,?,?,?,0)",
                           (body.bin_id, "warning", "Dispatch weight mismatch", f"Store scale and vendor receipt differ by {gap:.1f}%. Review the handover.", at))
        return {"ok": True, "id": db.execute("SELECT last_insert_rowid()").fetchone()[0]}

@app.get("/api/dispatches")
def get_dispatches():
    data = rows("SELECT d.*, b.name AS bin_name FROM dispatches d LEFT JOIN bins b ON b.id=d.bin_id ORDER BY dispatched_at DESC")
    for d in data:
        vals = [d.get("store_scale_kg"), d.get("vendor_receipt_kg")]
        d["gap_percent"] = None if None in vals or not d["store_scale_kg"] else round(abs(vals[0]-vals[1])/vals[0]*100, 2)
    return data

@app.get("/api/deposits/export.csv")
def export_deposits():
    data = rows("SELECT d.id,d.bin_id,b.name AS bin_name,d.weight_g,d.deposited_at,d.user_name,d.experiment,d.attribution_status,d.event_source FROM deposits d LEFT JOIN bins b ON b.id=d.bin_id ORDER BY d.deposited_at DESC")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id","bin_id","bin_name","weight_g","deposited_at","user_name","experiment","attribution_status","event_source"])
    writer.writeheader()
    writer.writerows(data)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ecotwin-deposits.csv"})
