import os.path
import datetime as dt

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main():
    print("✅ Script started")

    creds = None

    # Load existing token
    if os.path.exists("token.json"):
        print("🔐 Found token.json, loading saved credentials...")
        creds = Credentials.from_authorized_user_file("token.json")
    else:
        print("ℹ️ token.json not found, will log in fresh.")

    # If no valid credentials, login again
    if not creds or not creds.valid:
        print("🔄 Credentials missing or invalid, refreshing/login...")
        if creds and creds.expired and creds.refresh_token:
            print("🔁 Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("🌐 Opening browser for Google login...")
            flow = InstalledAppFlow.from_client_secrets_file(
                r"C:\Users\Admin\OneDrive\Desktop\Project\Python\current\credentials.json",
                SCOPES,
            )

            creds = flow.run_local_server(port=0)

        # Save the credentials for next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        print("💾 Saved new credentials to token.json")

    try:
        print("⚙️  Building Google Calendar service...")
        service = build("calendar", "v3", credentials=creds)

        # Get today's date/time
        now = dt.datetime.now().isoformat() + "Z"
        print("⏰ Time now (RFC3339-ish):", now)

        print("📅 Getting upcoming 10 events...")
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=5,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            print("😶 No upcoming events found.")
        else:
            print(f"✅ Found {len(events)} upcoming event(s):")
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                print(f" - {start} :: {event.get('summary', '(no title)')}")

    except HttpError as error:
        print("❌ An error occurred:", error)

    # 👇 This keeps the window open if you run by double-clicking the file
    input("\nPress Enter to close...")


if __name__ == "__main__":
    main()
