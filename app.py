import os
import json
import datetime as dt
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

from flask import Flask, request, jsonify
from flask_cors import CORS

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ---------------- CONFIG ----------------
SCOPES = ["https://www.googleapis.com/auth/calendar"]

app = Flask(__name__)
CORS(app)


# ---------------- HEALTH CHECK ----------------
@app.route("/")
def home():
    return "Backend is running 🚀"


# ---------------- GOOGLE CALENDAR (SERVICE ACCOUNT) ----------------
def get_calendar_service():
    creds_json = json.loads(os.environ["GC_SERVICE_ACCOUNT"])
    creds = Credentials.from_service_account_info(
        creds_json,
        scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


# ---------------- AVAILABLE SLOTS (STATIC & SAFE) ----------------
@app.get("/available-slots")
def available_slots():
    try:
        date_str = request.args.get("date")
        if not date_str:
            return jsonify({"slots": []})

        service = get_calendar_service()

        candidate_slots = [
            "08:00", "09:00", "10:00", "11:00",
            "14:00", "15:00", "16:00", "17:00"
        ]

        now = dt.datetime.now(IST)
        buffer_time = now + dt.timedelta(minutes=30)
        today_str = now.date().isoformat()

        date = dt.date.fromisoformat(date_str)

        time_min = dt.datetime.combine(date, dt.time.min, tzinfo=IST).isoformat()
        time_max = dt.datetime.combine(date, dt.time.max, tzinfo=IST).isoformat()

        events = service.events().list(
            calendarId="cuurehealth@gmail.com",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True
        ).execute().get("items", [])

        busy_ranges = []
        for e in events:
            if "dateTime" in e["start"]:
                start = dt.datetime.fromisoformat(e["start"]["dateTime"])
                end = dt.datetime.fromisoformat(e["end"]["dateTime"])
                busy_ranges.append((start, end))

        free_slots = []

        for slot in candidate_slots:
            slot_start = dt.datetime.fromisoformat(
                f"{date_str}T{slot}"
            ).replace(tzinfo=IST)
            slot_end = slot_start + dt.timedelta(minutes=30)

            # 🔒 Rule 1: Minimum 30-minute buffer for today
            if date_str == today_str and slot_start <= buffer_time:
                continue

            # 🔒 Rule 2: Prevent double booking
            overlap = any(
                not (slot_end <= b_start or slot_start >= b_end)
                for b_start, b_end in busy_ranges
            )

            if not overlap:
                free_slots.append(slot)

        return jsonify({"slots": free_slots})

    except Exception as e:
        print("Slots error:", e)
        return jsonify({"slots": []}), 500

# ---------------- CREATE APPOINTMENT (REAL GC EVENT) ----------------
@app.post("/create-appointment")
def create_appointment():
    try:
        data = request.get_json()

        start = dt.datetime.fromisoformat(f"{data['date']}T{data['time']}").replace(tzinfo=IST)
        end = start + dt.timedelta(minutes=30)

        service = get_calendar_service()

        # 🔒 DOUBLE BOOKING CHECK
        events = service.events().list(
            calendarId="cuurehealth@gmail.com",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True
        ).execute().get("items", [])

        if events:
            return jsonify({
                "status": "error",
                "error": "This slot is already booked"
            }), 409

        event = {
            "summary": f"Appointment - {data['name']}",
            "description": data.get("notes", ""),
            "start": {
                "dateTime": start.isoformat(),
                "timeZone": "Asia/Kolkata"
            },
            "end": {
                "dateTime": end.isoformat(),
                "timeZone": "Asia/Kolkata"
            }
        }

        service.events().insert(
            calendarId="cuurehealth@gmail.com",
            body=event
        ).execute()

        return jsonify({"status": "success"})

    except Exception as e:
        print("Booking error:", e)
        return jsonify({
            "status": "error",
            "error": "Could not book appointment"
        }), 500


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
