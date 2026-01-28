from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
import pytz 
import qrcode
from io import BytesIO
import models
from database import SessionLocal, engine

# Initialize Database Tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Define Canada Timezone (Eastern Time)
CANADA_TZ = pytz.timezone('America/Toronto')

# Helper function to get current time in Canada (as a naive object for DB compatibility)
def get_canada_time_naive():
    # We get the time in Toronto but remove timezone info (replace tzinfo=None)
    # This prevents the "offset-naive and offset-aware" crash during subtraction
    return datetime.now(CANADA_TZ).replace(tzinfo=None)

# Enable CORS for React Frontend (Vite uses 5173, standard React uses 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173", 
        "http://192.168.1.7:5173",
        "http://192.168.1.7:3000",
        "https://attendance-tracker-frontend-psi.vercel.app",
        "*" # Keep this during testing to ensure connectivity
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- STUDENT: SIGN IN ---
@app.post("/attendance/signin")
def sign_in(data: dict, db: Session = Depends(get_db)):
    new_record = models.AttendanceRecord(
        student_name=data.get("name", "Unknown Student"),
        sign_in=get_canada_time_naive(), 
        status="In-Progress",
        is_regularized=False
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return {"record_id": new_record.id, "message": "Clocked In (Toronto Time)"}

# --- STUDENT: SIGN OUT ---
@app.post("/attendance/signout/{record_id}")
def sign_out(record_id: int, db: Session = Depends(get_db)):
    record = db.query(models.AttendanceRecord).filter(models.AttendanceRecord.id == record_id).first()
    if not record: 
        raise HTTPException(status_code=404, detail="Session ID not found")
    
    # Save the sign out time
    record.sign_out = get_canada_time_naive()
    
    # Calculate duration (Both are now naive datetimes, so no crash!)
    duration = record.sign_out - record.sign_in
    seconds = int(duration.total_seconds())
    
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    record.total_hours = f"{hours}h {minutes}m"
    
    # Logic: Mark Present if at least 45 minutes worked
    record.status = "Present" if (hours > 0 or minutes >= 45) else "Shortage"
    
    db.commit()
    return {"status": record.status, "duration": record.total_hours}

# --- STUDENT: REGULARIZATION REQUEST ---
@app.post("/attendance/regularize")
async def request_regularization(data: dict, db: Session = Depends(get_db)):
    new_reg = models.AttendanceRecord(
        student_name=data.get("name", "Unknown Student"),
        sign_in=get_canada_time_naive(), 
        status="Pending Approval",
        notes=f"Date: {data.get('date')} | Reason: {data.get('reason')}",
        is_regularized=True
    )
    db.add(new_reg)
    db.commit()
    return {"message": "Submitted to Professor"}

# --- STUDENT: CALENDAR DATA ---
@app.get("/attendance/month-summary")
def get_month_summary(db: Session = Depends(get_db)):
    records = db.query(models.AttendanceRecord).all()
    summary = {}
    for r in records:
        if r.sign_in:
            date_key = r.sign_in.strftime("%Y-%m-%d")
            summary[date_key] = r.status
    return summary

# --- ACTIVITY FEED ---
@app.get("/activities")
def get_activities(db: Session = Depends(get_db)):
    records = db.query(models.AttendanceRecord).order_by(models.AttendanceRecord.sign_in.desc()).limit(10).all()
    activity_list = []
    for r in records:
        status_text = f"{r.student_name}: Clocked {r.status}"
        activity_list.append({
            "id": r.id,
            "text": status_text,
            "time": r.sign_in.strftime("%b %d, %I:%M %p") if r.sign_in else "N/A"
        })
    return activity_list

@app.get("/attendance")
def get_attendance_count(db: Session = Depends(get_db)):
    # Counts only rows marked 'Present'
    total_present = db.query(models.AttendanceRecord).filter(models.AttendanceRecord.status == "Present").count()
    return {"count": total_present}

# --- PROFESSOR ACTIONS ---
@app.get("/professor/pending")
def get_pending_requests(db: Session = Depends(get_db)):
    return db.query(models.AttendanceRecord).filter(models.AttendanceRecord.status == "Pending Approval").all()

@app.put("/professor/action/{record_id}")
def update_status(record_id: int, action: dict, db: Session = Depends(get_db)):
    record = db.query(models.AttendanceRecord).filter(models.AttendanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if action.get("status") == "Approved":
        record.status = "Present"
        record.notes = f"Approved: {record.notes}"
    else:
        record.status = "Rejected"
        
    db.commit()
    return {"message": f"Request {action.get('status')}"}

# --- QR CODE ---
@app.get("/attendance/qrcode")
def get_qrcode():
    data = "http://192.168.1.7:5173/tracker" # Updated for Vite port
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")