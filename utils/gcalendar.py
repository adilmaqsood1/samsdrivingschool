from pathlib import Path

from django.conf import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    service_account_file = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", None)
    if not service_account_file:
        service_account_file = str(Path(settings.BASE_DIR) / "service_account.json")

    credentials = service_account.Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
    return build("calendar", "v3", credentials=credentials)
