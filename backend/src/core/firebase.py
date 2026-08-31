"""Firebase Admin SDK lifecycle.

Separated from security.py on purpose: initializing the SDK is a process
concern, verifying a token is a request concern. Splitting them makes token
verification unit-testable with a faked verifier.
"""

import json
import threading

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

from src.core.config import Settings
from src.core.logger import get_logger

logger = get_logger(__name__)

_APP_NAME = "note-insight"
_init_lock = threading.Lock()


def _build_credential(settings: Settings) -> credentials.Base | None:
    """Return an explicit credential, or None to fall back to ADC/emulator.

    The service account arrives as a JSON string in an environment variable.
    No service-account file is ever written to disk or into the image.
    """
    if not settings.firebase_service_account_json:
        return None

    try:
        payload = json.loads(settings.firebase_service_account_json)
    except json.JSONDecodeError as exc:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    return credentials.Certificate(payload)


def initialize_firebase(settings: Settings) -> firebase_admin.App:
    """Idempotent, thread-safe initialization of the named Admin SDK app."""
    with _init_lock:
        try:
            return firebase_admin.get_app(_APP_NAME)
        except ValueError:
            pass

        credential = _build_credential(settings)
        options = (
            {"projectId": settings.firebase_project_id} if settings.firebase_project_id else {}
        )

        app = firebase_admin.initialize_app(credential, options, name=_APP_NAME)
        logger.info(
            "firebase_initialized",
            extra={
                "project_id": settings.firebase_project_id,
                "explicit_credential": credential is not None,
            },
        )
        return app


def get_firestore_client(settings: Settings) -> FirestoreClient:
    client: FirestoreClient = firestore.client(initialize_firebase(settings))
    return client
