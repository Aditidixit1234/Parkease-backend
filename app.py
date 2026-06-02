from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil, os, json, time, smtplib, bcrypt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ultralytics import YOLO
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── PATHS ───────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR          = os.path.dirname(BASE_DIR)
DATA_FILE         = os.path.join(ROOT_DIR, "processed_data", "results.json")
UPLOAD_DIR        = os.path.join(BASE_DIR, "uploads")
RESERVATIONS_FILE = os.path.join(ROOT_DIR, "processed_data", "reservations.json")
USERS_FILE        = os.path.join(ROOT_DIR, "processed_data", "users.json")

# ─── YOLO ────────────────────────────────────────────────
model = YOLO("yolov8n.pt")
VEHICLE_CLASSES = [2, 3, 5, 7]

# ─── SLOTS ───────────────────────────────────────────────
TOTAL_SLOTS = {
    "campus6":120, "campus12":80,  "campus13":100,
    "campus14":60, "campus15":90,  "campus25":70
}

# ─── TWILIO ──────────────────────────────────────────────
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

# ─── FILE HELPERS ────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def load_reservations():
    return load_json(RESERVATIONS_FILE, [])

def save_reservations(data):
    save_json(RESERVATIONS_FILE, data)

def load_users():
    return load_json(USERS_FILE, {})

def save_users(data):
    save_json(USERS_FILE, data)

def get_reserved_count(campus):
    return sum(1 for r in load_reservations() if r["campus"] == campus)

# ─── EMAIL ───────────────────────────────────────────────
def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"]    = os.getenv("GMAIL_USER")
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("GMAIL_USER"), os.getenv("GMAIL_PASS"))
            server.send_message(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Email failed: {e}")

# ─── SMS ─────────────────────────────────────────────────
def send_sms(to_phone, message):
    try:
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=to_phone
        )
        print(f"SMS sent to {to_phone}")
    except Exception as e:
        print(f"SMS failed: {e}")

# ═══════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════

@app.post("/login")
def login(username: str, password: str):
    users = load_users()
    if username not in users:
        raise HTTPException(status_code=401, detail="User not found")
    user = users[username]
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        raise HTTPException(status_code=401, detail="Wrong password")
    return {
        "success":  True,
        "username": username,
        "role":     user["role"],
        "email":    user["email"],
        "phone":    user["phone"]
    }

# ═══════════════════════════════════════════════════════════
# PARKING
# ═══════════════════════════════════════════════════════════

@app.get("/get-data")
def get_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

@app.post("/update-slots")
def update_slots(campus: str, slots: int):
    config_path = os.path.join(ROOT_DIR, "config.json")
    config = load_json(config_path, {})
    config[campus] = int(slots)
    save_json(config_path, config)
    return {"message": "Slots updated"}

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, file.filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    results = model(path)
    count = 0
    for r in results:
        if r.boxes is not None:
            for cls in r.boxes.cls:
                if int(cls) in VEHICLE_CLASSES:
                    count += 1

    total_slots = 120
    empty_slots = total_slots - count

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    campus = "campus6"
    if campus in data:
        for t in ["morning", "afternoon", "evening"]:
            data[campus][t] = count

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return {
        "vehicles":    count,
        "total_slots": total_slots,
        "empty_slots": empty_slots,
        "campus":      campus
    }

@app.post("/reserve")
def reserve(user: str, campus: str):
    users        = load_users()
    reservations = load_reservations()

    # check duplicate
    if any(r["user"] == user for r in reservations):
        return {"success": False, "message": "You already have an active reservation!"}

    # check slots
    reserved_count = get_reserved_count(campus)
    total = TOTAL_SLOTS.get(campus, 60)
    if reserved_count >= total:
        return {"success": False, "message": f"{campus} is FULL!"}

    # save
    reservation = {
        "user":      user,
        "role":      users[user]["role"] if user in users else "unknown",
        "campus":    campus,
        "time":      300,
        "booked_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    reservations.append(reservation)
    save_reservations(reservations)

    slots_left = total - reserved_count - 1

    # notify
    if user in users:
        u = users[user]

        send_email(
            u["email"],
            "Parking Reserved - Smart Parking",
            f"""
            <div style="font-family:'Segoe UI';max-width:500px;margin:auto;
                        background:#0f2027;color:white;border-radius:15px;padding:30px;">
                <h2 style="color:#00ffcc;">
                    Reservation Confirmed!
                </h2>
                <p>Hi <b>{user}</b>, your slot is booked.</p>
                <table style="width:100%;border-collapse:collapse;margin-top:15px;">
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.1);">
                        <td style="padding:10px;color:#aaa;">Campus</td>
                        <td style="padding:10px;color:#00ffcc;"><b>{campus}</b></td>
                    </tr>
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.1);">
                        <td style="padding:10px;color:#aaa;">Role</td>
                        <td style="padding:10px;">{u['role']}</td>
                    </tr>
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.1);">
                        <td style="padding:10px;color:#aaa;">Time</td>
                        <td style="padding:10px;">{reservation['booked_at']}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px;color:#aaa;">Slots Left</td>
                        <td style="padding:10px;">{slots_left}</td>
                    </tr>
                </table>
                <p style="color:#ff4d4d;margin-top:20px;">
                    Your slot expires in 5 minutes. Please arrive on time.
                </p>
            </div>
            """
        )

        send_sms(
            u["phone"],
            f"Smart Parking: Slot reserved at {campus}! "
            f"Time: {reservation['booked_at']}. "
            f"Expires in 5 mins. Slots left: {slots_left}"
        )

    return {
        "success":    True,
        "message":    f"Reserved at {campus}!",
        "slots_left": slots_left
    }

@app.get("/get-reservations")
def get_reservations():
    return load_reservations()

@app.post("/cancel-reservation")
def cancel_reservation(user: str):
    reservations = load_reservations()
    reservations = [r for r in reservations if r["user"] != user]
    save_reservations(reservations)

    users = load_users()
    if user in users:
        u = users[user]
        send_email(
            u["email"],
            "Reservation Cancelled - Smart Parking",
            f"""
            <div style="font-family:'Segoe UI';max-width:500px;margin:auto;
                        background:#0f2027;color:white;border-radius:15px;padding:30px;">
                <h2 style="color:#ff4d4d;">Reservation Cancelled</h2>
                <p>Hi <b>{user}</b>, your reservation has been cancelled.</p>
                <p style="color:#aaa;">You can make a new reservation anytime.</p>
            </div>
            """
        )
        send_sms(
            u["phone"],
            f"Smart Parking: Your reservation at has been cancelled. Book again anytime."
        )

    return {"message": "Cancelled"}