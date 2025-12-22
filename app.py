import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

import datetime as dt
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "token.json"

app = Flask(__name__)
CORS(app)

# ---------------- AUTH ----------------
def get_flow():
    return Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        redirect_uri="http://localhost:5000/oauth2callback"
    )

@app.get("/authorize")
def authorize():
    flow = get_flow()
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return redirect(url)

@app.get("/oauth2callback")
def oauth2callback():
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)

    with open(TOKEN_FILE, "w") as f:
        f.write(flow.credentials.to_json())

    return "✅ Calendar connected. You can close this tab."
@app.route("/")
def home():
    return "Backend is running 🚀"

# ---------------- CALENDAR ----------------
def get_calendar_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

# ---------------- AVAILABLE SLOTS ----------------
@app.get("/available-slots")
def available_slots():
    date_str = request.args.get("date")  # EXPECTS YYYY-MM-DD
    if not date_str:
        return jsonify({"slots": []})

    service = get_calendar_service()

    candidate_times = [
        "08:00", "09:00", "10:00", "11:00",
        "14:00", "15:00", "16:00", "17:00"
    ]

    date = dt.date.fromisoformat(date_str)

    time_min = dt.datetime.combine(date, dt.time.min).isoformat() + "Z"
    time_max = dt.datetime.combine(date, dt.time.max).isoformat() + "Z"

    events = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True
    ).execute().get("items", [])

    busy = []
    for e in events:
        if "dateTime" in e["start"]:
            s = dt.datetime.fromisoformat(e["start"]["dateTime"].replace("Z", ""))
            e_ = dt.datetime.fromisoformat(e["end"]["dateTime"].replace("Z", ""))
            busy.append((s, e_))

    free_slots = []
    for t in candidate_times:
        start = dt.datetime.fromisoformat(f"{date_str}T{t}")
        end = start + dt.timedelta(minutes=30)

        overlap = any(
            not (end <= b_start or start >= b_end)
            for b_start, b_end in busy
        )

        if not overlap:
            free_slots.append(t)

    return jsonify({"slots": free_slots})

# ---------------- CREATE APPOINTMENT ----------------
@app.post("/create-appointment")
def create_appointment():
    data = request.get_json()

    start = dt.datetime.fromisoformat(f"{data['date']}T{data['time']}")
    end = start + dt.timedelta(minutes=30)

    service = get_calendar_service()

    event = {
        "summary": f"Appointment - {data['name']}",
        "description": data.get("reason", ""),
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Kolkata"},
    }

    service.events().insert(calendarId="primary", body=event).execute()
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
