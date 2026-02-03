import os
import sys
import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

ARCHIVIST_API_KEY = os.getenv("ARCHIVIST_API_KEY")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import data_mgr

ARCHIVIST_API_KEY = os.getenv("ARCHIVIST_API_KEY")
BASE_URL = "https://api.myarchivist.ai/v1"


def _archivist_get(path: str, params: dict | None = None) -> dict:
    if not ARCHIVIST_API_KEY:
        raise RuntimeError("ARCHIVIST_API_KEY fehlt. Setze ihn in .env oder in deiner Shell.")

    url = f"{BASE_URL}{path}"
    headers = {"x-api-key": ARCHIVIST_API_KEY}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def find_archivist_campaign_id_by_title(title: str) -> str:
    # GET /v1/campaigns
    data = _archivist_get("/campaigns", params={"page": 1, "size": 50})
    for camp in data.get("data", []):
        if camp.get("title") == title:
            return camp["id"]
    raise RuntimeError(f"Archivist campaign mit title='{title}' nicht gefunden.")


def get_latest_session_summary(archivist_campaign_id: str) -> tuple[str, str]:
    # GET /v1/sessions?campaign_id=...
    data = _archivist_get("/sessions", params={"campaign_id": archivist_campaign_id, "page": 1, "size": 50})
    sessions = data.get("data", [])

    if not sessions:
        raise RuntimeError("Keine Sessions in Archivist gefunden.")

    # „Letzte Session“: wir nehmen die mit der neuesten session_date (Fallback created_at)
    def sort_key(s: dict) -> str:
        return s.get("session_date") or s.get("created_at") or ""

    latest = max(sessions, key=sort_key)

    session_title = latest.get("title") or "(untitled)"
    summary = latest.get("summary") or ""

    if not summary.strip():
        raise RuntimeError("Die letzte Archivist-Session hat keine summary (oder sie ist leer).")

    return session_title, summary


def find_local_campaign_id_by_name(name: str) -> int:
    campaigns = data_mgr.get_all_campaigns()
    for c in campaigns:
        if c["name"] == name:
            return int(c["id"])
    raise RuntimeError(f"Lokale campaign '{name}' nicht gefunden. (SQLite campaigns Tabelle)")


def main():
    # Ensure all tables exist before we read/write.
    data_mgr.init_db()

    campaign_title = "Tales of Aanur"

    # 1) Lokale Campaign-ID (int) finden
    local_campaign_id = find_local_campaign_id_by_name(campaign_title)

    # 2) Archivist Campaign-ID (string) finden
    archivist_campaign_id = find_archivist_campaign_id_by_title(campaign_title)

    # 3) Letzte Summary holen
    session_title, summary = get_latest_session_summary(archivist_campaign_id)

    # 4) In deine lokale sessions Tabelle speichern (content Feld)
    content_to_store = f"Archivist Summary — {session_title}\n\n{summary}"
    new_session_id = data_mgr.add_session(local_campaign_id, content_to_store)

    print(f"OK: gespeichert als lokale Session ID={new_session_id} (campaign_id={local_campaign_id}).")


if __name__ == "__main__":
    main()