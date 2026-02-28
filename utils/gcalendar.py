from pathlib import Path

from django.conf import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_oauth_calendar_service(user):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or ""
    client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or ""
    token_uri = getattr(settings, "GOOGLE_OAUTH_TOKEN_URI", "") or "https://oauth2.googleapis.com/token"
    if not (client_id and client_secret):
        return None

    from crm.models import CalendarAccount

    account = (
        CalendarAccount.objects.filter(owner=user, provider="google", active=True)
        .exclude(access_token="")
        .order_by("-created_at")
        .first()
    )
    if not account:
        return None

    credentials = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token or None,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    if account.token_expires_at:
        credentials.expiry = account.token_expires_at

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        account.access_token = credentials.token or ""
        account.token_expires_at = credentials.expiry
        account.save(update_fields=["access_token", "token_expires_at"])

    return build("calendar", "v3", credentials=credentials)


def get_calendar_service(user=None):
    if user:
        service = _get_oauth_calendar_service(user)
        if service:
            return service

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    service_account_file = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", None)
    if not service_account_file:
        service_account_file = str(Path(settings.BASE_DIR) / "service_account.json")

    credentials = service_account.Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
    return build("calendar", "v3", credentials=credentials)


def upsert_event(service, title, start, end, calendar_id=None, time_zone=None, google_event_id=None):
    from googleapiclient.errors import HttpError

    tz = time_zone or getattr(settings, "GOOGLE_CALENDAR_TIME_ZONE", "") or "UTC"
    cid = calendar_id or "primary"
    body = {
        "summary": title,
        "start": {"dateTime": start.isoformat(), "timeZone": tz},
        "end": {"dateTime": end.isoformat(), "timeZone": tz},
    }

    if google_event_id:
        try:
            service.events().update(calendarId=cid, eventId=google_event_id, body=body).execute()
            return google_event_id
        except HttpError as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            if status == 404 and cid and cid != "primary":
                try:
                    service.events().update(calendarId="primary", eventId=google_event_id, body=body).execute()
                    return google_event_id
                except HttpError as inner:
                    inner_status = getattr(getattr(inner, "resp", None), "status", None)
                    if inner_status != 404:
                        raise
            if status != 404:
                raise

    try:
        event = service.events().insert(calendarId=cid, body=body).execute()
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        if status == 404 and cid and cid != "primary":
            event = service.events().insert(calendarId="primary", body=body).execute()
        else:
            raise
    return event.get("id", "") or ""


def list_events(service, calendar_id=None, time_min=None, time_max=None, max_results=25):
    from googleapiclient.errors import HttpError

    cid = calendar_id or "primary"
    params = {"calendarId": cid, "singleEvents": True, "orderBy": "startTime", "maxResults": max(1, min(max_results, 2500))}
    if time_min:
        params["timeMin"] = time_min.isoformat()
    if time_max:
        params["timeMax"] = time_max.isoformat()
    try:
        return service.events().list(**params).execute()
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        if status == 404 and cid and cid != "primary":
            params["calendarId"] = "primary"
            return service.events().list(**params).execute()
        raise
