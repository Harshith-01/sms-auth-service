import os

import requests

NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "").rstrip("/")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "")
INTERNAL_SERVICE_NAME = os.getenv("INTERNAL_SERVICE_NAME", "auth-service")
TIMEOUT_SECONDS = 5


def send_email_notification(recipient_email: str, subject: str, body: str, event_type: str = "GENERIC") -> None:
    if not NOTIFICATION_SERVICE_URL or not INTERNAL_SERVICE_TOKEN:
        return

    payload = {
        "event_type": event_type,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "source_service": INTERNAL_SERVICE_NAME,
    }

    try:
        requests.post(
            f"{NOTIFICATION_SERVICE_URL}/notifications/email",
            json=payload,
            headers={
                "Authorization": f"Bearer {INTERNAL_SERVICE_TOKEN}",
                "X-Internal-Service": INTERNAL_SERVICE_NAME,
            },
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return
