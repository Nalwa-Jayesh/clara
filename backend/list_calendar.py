from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import pytz

class Calendar:
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    FILE_PATH = "credentials.json"

    def __init__(self):
        credentials = service_account.Credentials.from_service_account_file(
            filename=self.FILE_PATH, scopes=self.SCOPES
        )
        self.service = build("calendar", "v3", credentials=credentials)

    def get_calendar_list(self):
        return self.service.calendarList().list().execute()

    def add_calendar(self, calendar_id):
        calendar_list_entry = {"id": calendar_id}

        created_calendar = self.service.calendarList().insert(body=calendar_list_entry).execute()
        return created_calendar['id']

    def add_event(self, calendar_id, body):
        return self.service.events().insert(calendarId=calendar_id, body=body).execute()


"""event = {
    "summary": "Google I/O 2015",
    "location": "800 Howard St., San Francisco, CA 94103",
    "description": "A chance to hear more about Google's developer products.",
    "start": {
        "dateTime": "2025-07-01T09:00:00+05:30",
        "timeZone": "Asia/Kolkata",
    },
    "end": {
        "dateTime": "2025-07-01T17:00:00+05:30",
        "timeZone": "Asia/Kolkata",
    },
}"""

tz = pytz.timezone('Asia/Kolkata')
start_time = tz.localize(datetime.datetime(2025, 7, 1, 9, 0, 0))
end_time = tz.localize(datetime.datetime(2025, 7, 1, 17, 0, 0))

event = {
    'summary': "Test Event",
    'description': "Testing timezone-aware datetime",
    'start': {
        'dateTime': start_time.isoformat(),
        'timeZone': 'Asia/Kolkata',
    },
    'end': {
        'dateTime': end_time.isoformat(),
        'timeZone': 'Asia/Kolkata',
    },
}

obj = Calendar()
test_event = obj.add_event(calendar_id="nalwajayesh97@gmail.com", body=event)
print(f"id: {test_event}")
