SYSTEM_PROMPT = """
You are a co-Dungeon Master helping to prepare the next D&D 5e session.

Your role:
- Interpret session summaries accurately and consistently, maintaining internal logic and continuity.
- Identify unresolved tensions, character motivations, emotional undercurrents, and narrative threads that deserve continuation.
- Predict likely player intentions and offer multiple meaningful paths forward, each with distinct consequences and trade-offs.
- Maintain continuity with all previously established events, rules, lore, and world logic.
- Uphold emotional realism and moral complexity in NPC behavior, avoiding one‑dimensional portrayals.
- Enhance scenes with evocative, atmospheric detail when appropriate, supporting strong flavor and fantasy without unnecessary verbosity.
- Provide material that is immediately usable at the table: structured options, hooks, examples, and clear next steps.
- Use concise, readable formatting so the DM can quickly scan and apply your output in live play.
- Make emotional stakes visible—show how events impact characters internally, and why their choices matter.
- Clearly articulate the stakes behind each option: what happens if players choose X, Y, or an unexpected third path.
""".strip()


def _format_party_members(party_members) -> str:
    """Format the list of party members into a readable text block."""
    if not party_members:
        return "None selected."

    lines = []
    for member in party_members:
        name = member.get("name") or "Unknown"
        parts = []

        species = member.get("character_species")
        if species:
            parts.append(species)

        character_class = member.get("character_class")
        if character_class:
            parts.append(character_class)

        level = member.get("level")
        if level is not None:
            parts.append(f"Lv {level}")

        header = name
        if parts:
            header = f"{name} ({', '.join(parts)})"

        player_name = member.get("player_name")
        if player_name:
            header = f"{header} - Player: {player_name}"

        notes = member.get("notes")
        if notes:
            lines.append(f"- {header}\n  Notes: {notes}")
        else:
            lines.append(f"- {header}")

    return "\n".join(lines)


def _format_npcs(npcs) -> str:
    """Format the list of NPCs into a readable text block."""
    if not npcs:
        return "None selected."

    lines = []
    for npc in npcs:
        name = npc.get("name") or "Unknown"
        parts = []

        species = npc.get("species")
        if species:
            parts.append(species)

        gender = npc.get("gender")
        if gender:
            parts.append(gender)

        header = name
        if parts:
            header = f"{name} ({', '.join(parts)})"

        notes = npc.get("notes")
        if notes:
            lines.append(f"- {header}\n  Notes: {notes}")
        else:
            lines.append(f"- {header}")

    return "\n".join(lines)


def _format_locations(locations) -> str:
    """Format the list of locations into a readable text block."""
    if not locations:
        return "None selected."

    lines = []
    for loc in locations:
        name = loc.get("name") or "Unknown"
        parts = []

        location_type = loc.get("location_type")
        if location_type:
            parts.append(location_type)

        header = name
        if parts:
            header = f"{name} ({', '.join(parts)})"

        notes = loc.get("notes")
        if notes:
            lines.append(f"- {header}\n  Notes: {notes}")
        else:
            lines.append(f"- {header}")

    return "\n".join(lines)


def build_user_prompt(
    campaign_name: str,
    party_members,
    npcs,
    locations,
    last_session_text: str,
) -> str:
    """
    Build the user prompt message for the next-session prep generation.

    Args:
        campaign_name: Name of the campaign
        party_members: List of selected party member dicts
        npcs: List of selected NPC dicts
        locations: List of selected location dicts
        last_session_text: Full text of the previous session summary.

    Returns:
        A formatted user prompt string that instructs the model to generate
        practical prep material for the next session.
    """
    party_block = _format_party_members(party_members or [])
    npc_block = _format_npcs(npcs or [])
    location_block = _format_locations(locations or [])

    return f"""
SESSION SUMMARY
{last_session_text}

CAMPAIGN CONTEXT
- Campaign: {campaign_name}

SELECTED PARTY MEMBERS
{party_block}

SELECTED NPCS
{npc_block}

SELECTED LOCATIONS
{location_block}

CAMPAIGN THEMES
- Themes: autonomy vs. control, empire ethics, sentient constructs
- Tone: dramatic, morally gray, character-driven

TASK
Using the session summary and campaign context, prepare material for the NEXT SESSION.

IMPORTANT
Please respond entirely in German.

OUTPUT FORMAT (strict)
Use the exact section headings below. Under "VORSCHLAG 1–3", always provide three distinct variants.

1) VORSCHLAG 1
2) VORSCHLAG 2
3) VORSCHLAG 3

Each VORSCHLAG must include the following subsections:
- HOOKS (2–3 ideas)
- NPC FOCUS (max 3–4 NPCs)
- SCENES & SET PIECES (3–5 scenes)
- CONSEQUENCE BRANCHES (2–3 decisions)
- SHORT RECAP FOR PLAYERS (1 paragraph)

Please provide:

1) HIGH-LEVEL HOOKS (2–3 ideas)
- 2–3 different directions the next session could take.
- Each hook should clearly connect to unresolved tensions from the summary.

2) NPC FOCUS
- Key NPCs to highlight next session (max 3–4).
- For each, describe:
  - Current emotional state
  - Short-term goal (1–3 sessions)
  - Long-term agenda
  - One concrete way they might appear or influence the next scene.

3) SCENES & SET PIECES
- 3–5 possible scenes I can run next session.
- For each scene:
  - Title (1 line)
  - Setup (2–4 sentences)
  - What the players might DO (choices / approaches)
  - How the world/NPCs react
  - Optional skill checks or combat hooks (D&D 5e friendly, but rules-light).

4) CONSEQUENCE BRANCHES
- For 2–3 key decisions the players might make, outline:
  - If they do X, then…
  - If they refuse or fail, then…
  - If they find a third option, then… (suggest 1–2 examples).

5) SHORT RECAP FOR PLAYERS
- 1 short paragraph I can read aloud at the table as “Previously on…”.
- Written in a dramatic but clear style, no rules-talk.
""".strip()


def build_refine_prompt(user_prompt: str, ai_output_v1: str, feedback_text: str) -> str:
    """
    Build a follow-up prompt to refine the first output based on user feedback.
    """
    return f"""
ORIGINAL PROMPT
{user_prompt}

FIRST OUTPUT (V1)
{ai_output_v1}

USER FEEDBACK
{feedback_text}

TASK
Refine the output based on the user's feedback.
Keep the same OUTPUT FORMAT and respond entirely in German.
""".strip()
