import os
import unicodedata
import html

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from openai import OpenAI

import data_mgr
from prompts.session_prep_prompt import SYSTEM_PROMPT, build_user_prompt

# Load environment variables from a .env file
load_dotenv()

app = Flask(__name__)

# OpenAI config
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1")

# The OpenAI SDK will also read OPENAI_API_KEY from your environment.
# If you want, you can set it in .env as: OPENAI_API_KEY=...
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# -------------------------
# Validation helpers (Unicode-friendly)
# -------------------------

# Allowed punctuation for "name-like" fields.
_ALLOWED_NAME_PUNCT = {
    " ", "-", "_", ".", ",", ":", ";",
    "'", "’",  # straight + curly apostrophe
    "(", ")", "[", "]",
    "&", "/",
}

# Block angle brackets to reduce XSS problems later when you render templates.
_BLOCKED_CHARS = {"<", ">"}


def _is_control_char(ch: str) -> bool:
    """True if a character is a control character (including DEL)."""
    code = ord(ch)
    return code < 32 or code == 127


def _is_unicode_letter_or_number(ch: str) -> bool:
    """True for unicode letters (L*), marks (M*), and numbers (N*)."""
    cat = unicodedata.category(ch)
    return cat.startswith(("L", "M", "N"))


def _is_safe_name(text: str) -> bool:
    """Unicode-safe: letters/numbers + allowed punctuation; no control chars; no < or >."""
    if not text:
        return False

    for ch in text:
        if ch in _BLOCKED_CHARS:
            return False

        if _is_control_char(ch):
            return False

        if _is_unicode_letter_or_number(ch):
            continue

        if ch in _ALLOWED_NAME_PUNCT:
            continue

        # Reject everything else (e.g. emojis or unusual symbols)
        return False

    return True


def _clean_name(value, field_name, max_len=150, required=True):
    """Validate a name-like field (Unicode)."""
    value = (value or "").strip()

    if required and not value:
        raise ValueError(f"{field_name} is required.")

    if not value:
        return None

    if len(value) > max_len:
        raise ValueError(f"{field_name} is too long (max {max_len} chars).")

    if not _is_safe_name(value):
        raise ValueError(
            f"{field_name} has invalid characters. "
            "Allowed: letters/numbers (Unicode), spaces, and common punctuation "
            "(- _ ' ’ . , : ; ( ) [ ] & /). "
            "Also blocked: < > and control characters."
        )

    return value


def _clean_int(value, field_name, required=False, min_value=None, max_value=None):
    value = ("" if value is None else str(value)).strip()

    if required and not value:
        raise ValueError(f"{field_name} is required.")

    if not value:
        return None

    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number.") from exc

    if min_value is not None and number < min_value:
        raise ValueError(f"{field_name} must be at least {min_value}.")

    if max_value is not None and number > max_value:
        raise ValueError(f"{field_name} must be at most {max_value}.")

    return number


def _clean_long_text(value, field_name, max_len=50000, required=False):
    """Allow Unicode long text, but block control chars and < >."""
    value = (value or "").strip()

    if required and not value:
        raise ValueError(f"{field_name} is required.")

    if not value:
        return None

    if len(value) > max_len:
        raise ValueError(f"{field_name} is too long (max {max_len} chars).")

    for ch in value:
        if ch in _BLOCKED_CHARS:
            raise ValueError(f"{field_name} contains blocked characters: < or >.")

        if ch in ("\n", "\r", "\t"):
            continue

        if _is_control_char(ch):
            raise ValueError(f"{field_name} contains invalid control characters.")

    return value


def _payload():
    """Read JSON if present, otherwise fall back to form data."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict(flat=True)


def _ok(data=None, status=200):
    body = {"ok": True}
    if data:
        body.update(data)
    return jsonify(body), status


def _err(message, status=400):
    return jsonify({"ok": False, "error": message}), status


def _require(func_name: str):
    """Return a function from data_mgr or raise a helpful error."""
    fn = getattr(data_mgr, func_name, None)
    if fn is None:
        raise RuntimeError(
            f"Missing function in data_mgr.py: {func_name}. "
            "Add it to data_mgr.py (CRUD) and try again."
        )
    return fn


# -------------------------
# OpenAI helper
# -------------------------

def call_chatgpt(user_prompt):
    """Call the model and return the text output."""
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as exc:
        # Keep it simple for beginners: return an error message the UI can show.
        return f"Error calling OpenAI: {exc}"


# -------------------------
# UI routes (existing)
# -------------------------

@app.route("/", methods=["GET"])
def index():
    """Show the start page with a campaign dropdown."""
    try:
        campaigns = _require("get_all_campaigns")()
    except Exception as exc:
        print("Error loading campaigns:", exc)
        campaigns = []

    error = request.args.get("error")
    return render_template("index.html", campaigns=campaigns, error=error)

@app.route("/generate", methods=["POST"])
def generate_session():
    """Generate a new session idea from the last stored session transcript."""
    campaign_id = request.form.get("campaign_id")

    if not campaign_id:
        return redirect(url_for("index", error="Please select a campaign first."))

    # Convert to int if possible (helps avoid confusing bugs)
    try:
        campaign_id_int = int(campaign_id)
    except ValueError:
        return redirect(url_for("index", error="Invalid campaign ID."))

    try:
        campaign_data = _require("get_campaign_last_session")(campaign_id_int)
    except Exception as exc:
        print("Error loading last session:", exc)
        return redirect(url_for("index", error="Error loading campaign data."))

    if not campaign_data or not campaign_data.get("last_session_text"):
        return redirect(url_for("index", error="No stored session found for this campaign."))

    campaign_name = campaign_data.get("name", f"Campaign {campaign_id_int}")
    last_session_text = campaign_data["last_session_text"]

    user_prompt = build_user_prompt(campaign_name, last_session_text)
    ai_output = call_chatgpt(user_prompt)

    return render_template(
        "session_prep.html",
        campaign_name=campaign_name,
        ai_output=ai_output,
    )


# -------------------------
# API: Helpers for the landing page
# -------------------------

@app.route("/api/campaigns/<int:campaign_id>/last-session", methods=["GET"])
def api_campaign_last_session(campaign_id):
    """Return the last stored session text for a campaign.

    This is a small helper endpoint for the landing page UI.
    It returns JSON like:
    {
      ok: true,
      campaign: {id, name},
      last_session_text: "..."
    }

    If there is no stored session yet, last_session_text will be an empty string.
    """
    try:
        data = _require("get_campaign_last_session")(campaign_id)
        if data is None:
            return _err("Campaign not found.", 404)

        return _ok(
            {
                "campaign": {"id": campaign_id, "name": data.get("name")},
                "last_session_text": data.get("last_session_text") or "",
            }
        )
    except Exception as exc:
        return _err(str(exc), 500)

# -------------------------
# API: Campaigns (CRUD)
# -------------------------

@app.route("/api/campaigns", methods=["GET"])
def api_campaigns_list():
    try:
        campaigns = _require("get_all_campaigns")()
        return _ok({"campaigns": campaigns})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns", methods=["POST"])
def api_campaigns_create():
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=100, required=True)
        new_id = _require("add_campaign")(name)
        return _ok({"id": new_id}, 201)
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>", methods=["GET"])
def api_campaigns_get(campaign_id):
    try:
        campaign = _require("get_campaign_by_id")(campaign_id)
        if campaign is None:
            return _err("Campaign not found.", 404)
        return _ok({"campaign": campaign})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>", methods=["POST"])
def api_campaigns_update(campaign_id):
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=100, required=True)
        updated = _require("update_campaign")(campaign_id, name)
        if not updated:
            return _err("Campaign could not be updated.", 404)
        return _ok()
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/delete", methods=["POST"])
def api_campaigns_delete(campaign_id):
    try:
        deleted = _require("delete_campaign")(campaign_id)
        if not deleted:
            return _err("Campaign could not be deleted.", 404)
        return _ok()
    except Exception as exc:
        return _err(str(exc), 500)


# -------------------------
# API: Sessions (CRUD)
# -------------------------

@app.route("/api/campaigns/<int:campaign_id>/sessions", methods=["GET"])
def api_sessions_list(campaign_id):
    try:
        sessions = _require("get_sessions_for_campaign")(campaign_id)
        return _ok({"sessions": sessions})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/sessions", methods=["POST"])
def api_sessions_create(campaign_id):
    data = _payload()
    try:
        content = _clean_long_text(data.get("content"), "content", max_len=50000, required=True)
        new_id = _require("add_session")(campaign_id, content)
        return _ok({"id": new_id}, 201)
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/sessions/<int:session_id>", methods=["GET"])
def api_sessions_get(campaign_id, session_id):
    try:
        session = _require("get_session_by_id")(campaign_id, session_id)
        if session is None:
            return _err("Session not found.", 404)
        return _ok({"session": session})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/sessions/<int:session_id>", methods=["POST"])
def api_sessions_update(campaign_id, session_id):
    data = _payload()
    try:
        content = _clean_long_text(data.get("content"), "content", max_len=50000, required=True)
        updated = _require("update_session")(campaign_id, session_id, content)
        if not updated:
            return _err("Session could not be updated.", 404)
        return _ok()
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/sessions/<int:session_id>/delete", methods=["POST"])
def api_sessions_delete(campaign_id, session_id):
    try:
        deleted = _require("delete_session")(campaign_id, session_id)
        if not deleted:
            return _err("Session could not be deleted.", 404)
        return _ok()
    except Exception as exc:
        return _err(str(exc), 500)


# -------------------------
# API: Party members (CRUD)
# -------------------------

@app.route("/api/campaigns/<int:campaign_id>/party", methods=["GET"])
def api_party_list(campaign_id):
    try:
        members = _require("get_party_members_for_campaign")(campaign_id)
        return _ok({"party_members": members})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/party", methods=["POST"])
def api_party_create(campaign_id):
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=100, required=True)
        player_name = _clean_name(data.get("player_name"), "player_name", max_len=100, required=False)
        character_species = _clean_name(
            data.get("character_species"), "character_species", max_len=100, required=False
        )
        character_class = _clean_name(
            data.get("character_class"), "character_class", max_len=100, required=False
        )
        level = _clean_int(data.get("level"), "level", required=False, min_value=0, max_value=30)
        notes = _clean_long_text(data.get("notes"), "notes", max_len=4000, required=False)

        new_id = _require("add_party_member")(
            campaign_id=campaign_id,
            name=name,
            player_name=player_name,
            character_species=character_species,
            character_class=character_class,
            level=level,
            notes=notes,
        )
        return _ok({"id": new_id}, 201)
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/party/<int:member_id>", methods=["GET"])
def api_party_get(campaign_id, member_id):
    try:
        member = _require("get_party_member_by_id")(campaign_id, member_id)
        if member is None:
            return _err("Party member not found.", 404)
        return _ok({"party_member": member})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/party/<int:member_id>", methods=["POST"])
def api_party_update(campaign_id, member_id):
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=100, required=True)
        player_name = _clean_name(data.get("player_name"), "player_name", max_len=100, required=False)
        character_species = _clean_name(
            data.get("character_species"), "character_species", max_len=100, required=False
        )
        character_class = _clean_name(
            data.get("character_class"), "character_class", max_len=100, required=False
        )
        level = _clean_int(data.get("level"), "level", required=False, min_value=0, max_value=30)
        notes = _clean_long_text(data.get("notes"), "notes", max_len=4000, required=False)

        updated = _require("update_party_member")(
            campaign_id=campaign_id,
            member_id=member_id,
            name=name,
            player_name=player_name,
            character_species=character_species,
            character_class=character_class,
            level=level,
            notes=notes,
        )
        if not updated:
            return _err("Party member could not be updated.", 404)

        return _ok()
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/party/<int:member_id>/delete", methods=["POST"])
def api_party_delete(campaign_id, member_id):
    try:
        deleted = _require("delete_party_member")(campaign_id, member_id)
        if not deleted:
            return _err("Party member could not be deleted.", 404)
        return _ok()
    except Exception as exc:
        return _err(str(exc), 500)


# -------------------------
# API: NPCs (CRUD)
# -------------------------

@app.route("/api/campaigns/<int:campaign_id>/npcs", methods=["GET"])
def api_npcs_list(campaign_id):
    try:
        npcs = _require("get_npcs_for_campaign")(campaign_id)
        return _ok({"npcs": npcs})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/npcs", methods=["POST"])
def api_npcs_create(campaign_id):
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=100, required=True)
        species = _clean_name(data.get("species"), "species", max_len=100, required=False)
        gender = _clean_name(data.get("gender"), "gender", max_len=50, required=False)
        notes = _clean_long_text(data.get("notes"), "notes", max_len=4000, required=False)

        new_id = _require("add_npc")(campaign_id, name, species=species, gender=gender, notes=notes)
        return _ok({"id": new_id}, 201)
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/npcs/<int:npc_id>", methods=["GET"])
def api_npcs_get(campaign_id, npc_id):
    try:
        npc = _require("get_npc_by_id")(campaign_id, npc_id)
        if npc is None:
            return _err("NPC not found.", 404)
        return _ok({"npc": npc})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/npcs/<int:npc_id>", methods=["POST"])
def api_npcs_update(campaign_id, npc_id):
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=100, required=True)
        species = _clean_name(data.get("species"), "species", max_len=100, required=False)
        gender = _clean_name(data.get("gender"), "gender", max_len=50, required=False)
        notes = _clean_long_text(data.get("notes"), "notes", max_len=4000, required=False)

        updated = _require("update_npc")(
            campaign_id=campaign_id,
            npc_id=npc_id,
            name=name,
            species=species,
            gender=gender,
            notes=notes,
        )
        if not updated:
            return _err("NPC could not be updated.", 404)

        return _ok()
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/campaigns/<int:campaign_id>/npcs/<int:npc_id>/delete", methods=["POST"])
def api_npcs_delete(campaign_id, npc_id):
    try:
        deleted = _require("delete_npc")(campaign_id, npc_id)
        if not deleted:
            return _err("NPC could not be deleted.", 404)
        return _ok()
    except Exception as exc:
        return _err(str(exc), 500)


# -------------------------
# API: Locations (CRUD) - global
# -------------------------

@app.route("/api/locations", methods=["GET"])
def api_locations_list():
    try:
        locations = _require("get_all_locations")()
        return _ok({"locations": locations})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/locations", methods=["POST"])
def api_locations_create():
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=150, required=True)
        location_type = _clean_name(data.get("location_type"), "location_type", max_len=50, required=False)
        notes = _clean_long_text(data.get("notes"), "notes", max_len=8000, required=False)

        new_id = _require("add_location")(name=name, location_type=location_type, notes=notes)
        return _ok({"id": new_id}, 201)
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/locations/<int:location_id>", methods=["GET"])
def api_locations_get(location_id):
    try:
        loc = _require("get_location_by_id")(location_id)
        if loc is None:
            return _err("Location not found.", 404)
        return _ok({"location": loc})
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/locations/<int:location_id>", methods=["POST"])
def api_locations_update(location_id):
    data = _payload()
    try:
        name = _clean_name(data.get("name"), "name", max_len=150, required=True)
        location_type = _clean_name(data.get("location_type"), "location_type", max_len=50, required=False)
        notes = _clean_long_text(data.get("notes"), "notes", max_len=8000, required=False)

        updated = _require("update_location")(
            location_id=location_id,
            name=name,
            location_type=location_type,
            notes=notes,
        )
        if not updated:
            return _err("Location could not be updated.", 404)

        return _ok()
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 500)


@app.route("/api/locations/<int:location_id>/delete", methods=["POST"])
def api_locations_delete(location_id):
    try:
        deleted = _require("delete_location")(location_id)
        if not deleted:
            return _err("Location could not be deleted.", 404)
        return _ok()
    except Exception as exc:
        return _err(str(exc), 500)


# -------------------------
# UI routes
# -------------------------

@app.route("/overview", methods=["POST"])
def overview():
    """Temporary overview placeholder page.

    Later we will replace this with a real Jinja template.
    """
    campaign_id = (request.form.get("campaign_id") or "").strip()
    party_ids = (request.form.get("party_ids") or "").strip()
    npc_ids = (request.form.get("npc_ids") or "").strip()
    location_ids = (request.form.get("location_ids") or "").strip()
    last_session_text = (request.form.get("last_session_text") or "").strip()

    return (
        "<html><body style='font-family: system-ui; max-width: 900px; margin: 24px auto;'>"
        "<h1>Overview (placeholder)</h1>"
        "<p>This is a temporary page so you can continue your workflow.</p>"
        f"<p><strong>Campaign ID:</strong> {html.escape(campaign_id)}</p>"
        f"<p><strong>Party IDs:</strong> {html.escape(party_ids)}</p>"
        f"<p><strong>NPC IDs:</strong> {html.escape(npc_ids)}</p>"
        f"<p><strong>Location IDs:</strong> {html.escape(location_ids)}</p>"
        "<h2>Last session text</h2>"
        f"<pre style='white-space: pre-wrap; background:#f7f7f7; padding:12px; border-radius:10px;'>{html.escape(last_session_text)}</pre>"
        "<p><a href='/'>← Back</a></p>"
        "</body></html>"
    )

# -------------------------
# Main
# -------------------------

if __name__ == "__main__":
    _require("init_db")()
    app.run(debug=True)