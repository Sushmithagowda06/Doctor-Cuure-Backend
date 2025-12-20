import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime as dt

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ================== PATH SETUP ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

SCOPES = ["https://www.googleapis.com/auth/calendar"]

app = Flask(__name__)
CORS(app)





# ================== GOOGLE CALENDAR SERVICE ==================
def get_calendar_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_FILE, SCOPES
            )
            creds = flow.run_local_server(
    port=0,
    prompt="consent",
    authorization_prompt_message="Please authorize Doctor Cuure to access calendar"
)


        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

# ================== SLOT CHECK (FREEBUSY) ==================
def is_slot_free(service, calendar_id, start_dt, end_dt):
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))

    start_ist = start_dt.replace(tzinfo=ist)
    end_ist = end_dt.replace(tzinfo=ist)

    body = {
        "timeMin": start_ist.isoformat(),
        "timeMax": end_ist.isoformat(),
        "timeZone": "Asia/Kolkata",
        "items": [{"id": calendar_id}],
    }

    freebusy = service.freebusy().query(body=body).execute()
    busy = freebusy["calendars"][calendar_id]["busy"]

    return len(busy) == 0

# ================== FULL DAY LEAVE CHECK ==================
def is_doctor_on_leave(service, calendar_id, date_obj):
    start = dt.datetime.combine(date_obj, dt.time.min).isoformat() + "Z"
    end = dt.datetime.combine(date_obj, dt.time.max).isoformat() + "Z"

    events = service.events().list(
        calendarId=calendar_id,
        timeMin=start,
        timeMax=end,
        singleEvents=True
    ).execute()

    for event in events.get("items", []):
        if "date" in event["start"]:  # ALL-DAY EVENT
            return True

    return False

# ================== CREATE APPOINTMENT ==================
@app.post("/create-appointment")
def create_appointment():
    try:
        data = request.get_json()

        name = data["name"]
        reason = data.get("reason", "")
        date_str = data["date"]
        time_str = data["time"]

        start_dt = dt.datetime.fromisoformat(f"{date_str}T{time_str}")
        end_dt = start_dt + dt.timedelta(minutes=30)

        service = get_calendar_service()
        calendar_id = "primary"
        date_obj = dt.date.fromisoformat(date_str)

        # 🚫 BLOCK FULL DAY LEAVE
        if is_doctor_on_leave(service, calendar_id, date_obj):
            return jsonify({
                "status": "error",
                "message": "Doctor is not available on this date"
            }), 409

        # 🚫 BLOCK BUSY SLOT
        if not is_slot_free(service, calendar_id, start_dt, end_dt):
            return jsonify({
                "status": "error",
                "message": "Doctor is not available for this time slot"
            }), 409

        event = {
            "summary": f"Appointment - {name}",
            "description": reason,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
        }

        created = service.events().insert(
            calendarId="primary",
            body=event
        ).execute()

        return jsonify({
            "status": "success",
            "eventId": created["id"]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ================== AVAILABLE SLOTS ==================
@app.get("/available-slots")
def available_slots():
    try:
        date_str = request.args.get("date")
        if not date_str:
            return jsonify({"status": "error", "message": "Missing date"}), 400

        date_obj = dt.date.fromisoformat(date_str)

        service = get_calendar_service()
        calendar_id = "primary"

        # 🚫 FULL DAY LEAVE → NO SLOTS
        if is_doctor_on_leave(service, calendar_id, date_obj):
            return jsonify({"status": "success", "slots": []})

        candidate_times = [
            "08:00", "09:00", "10:00", "11:00",
            "14:00", "15:00", "16:00", "17:00"
        ]

        free_slots = []

        for t in candidate_times:
            start_dt = dt.datetime.fromisoformat(f"{date_str}T{t}")
            end_dt = start_dt + dt.timedelta(minutes=30)

            if is_slot_free(service, calendar_id, start_dt, end_dt):
                free_slots.append(t)

        return jsonify({"status": "success", "slots": free_slots})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ================== RUN SERVER ==================
if __name__ == "__main__":
    app.run()
