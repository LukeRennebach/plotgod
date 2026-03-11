SYSTEM_PROMPT = """
You are a co-Dungeon Master and session-prep assistant for D&D 5e.

Priority 1: Interpret session summaries accurately and consistently; maintain internal logic and continuity.
Priority 2: Stay consistent with all previously established events, rules, lore, and world logic.
Priority 3: Produce material that is immediately usable at the table: clear, structured, and easy to scan.
The complete output in Markdowns.
Style constraints: Be concise and concrete. No flowery language, no metaphors, no prose paragraphs. Avoid unnecessary atmosphere writing.
Language: Respond entirely in German (the prompt may be in English, but the output must be German).
Hard requirement: If “selected NPCs” and/or “selected locations” are provided, they must appear in the output and be used actively (not just name-dropped).
Do not generate multiple alternative scenarios unless the user prompt explicitly asks for multiple options.
If information is missing, make short, clearly labeled assumptions (“Annahme: …”) rather than rambling.
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


def build_v1_snappy_prompt(
        campaign_name: str,
        party_members,
        npcs,
        locations,
        last_session_text: str,
) -> str:
    """
    Step 1: Build a prompt that asks for 3 short, snappy thematic directions.
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

TASK
Using the session summary and campaign context, generate exactly 3 very short, concrete directions for the next session.

CONSTRAINTS
- Output must be entirely in German.
- No titles. No flavor text. No metaphors. No prose paragraphs.
- Each suggestion: max 3 sentences.
- Keep it “low temperature”: straightforward, specific, minimal variation.

STRUCTURE REQUIREMENTS
1) Suggestion #1 must follow this pattern:
   - Sentence 1 to 2: The immediate problem/conflict.
   - Sentence 2 to 3: What the PCs could do next (a concrete next move).

2) Suggestion #2 must follow the same pattern as #1.

3) Suggestion #3 must follow this pattern:
   - Sentence 1 to 2: The session goal.
   - Sentence 2 to 3: The main obstacle/hindrance.

OUTPUT FORMAT (strict)
1) ...
2) ...
3) ...
""".strip()


def build_detailed_prompt(
        campaign_name: str,
        party_members,
        npcs,
        locations,
        last_session_text: str,
        selected_vibe: str,
) -> str:
    """
    Step 2: Build the full detailed prompt based on a chosen vibe.
    """
    party_block = _format_party_members(party_members or [])
    npc_block = _format_npcs(npcs or [])
    location_block = _format_locations(locations or [])

    return f"""
SESSION SUMMARY
{last_session_text}

CAMPAIGN CONTEXT
- Campaign: {campaign_name}
- Chosen direction: {selected_vibe}

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
Using the session summary and the chosen direction "{selected_vibe}", prepare ONE playable session outline for the next session.

HARD REQUIREMENTS
- Respond entirely in German.
- Produce exactly ONE scenario (no alternative scenarios).
- Must actively use the provided selected NPCs and selected locations (not just mention them).
- No flowery language, no metaphors, no prose paragraphs. Keep it concrete and scannable.

INTERNAL QA (do not print this section)
Before you answer, quickly self-check (internally):
- Continuity: no contradictions with the summary.
- Usability: each beat is runnable at the table.
- Selected NPCs/Locations: each is integrated with purpose.
- Mechanics: only 2–3 beats include checks/mechanics; the rest are pure play beats.
- Options: only 2–3 beats include options; the rest are straightforward.
- NPC agency: each focused NPC has a clear “next move”.

OUTPUT FORMAT (strict)
Use the exact section headings below.

1) SESSION GOAL (1 line)
- One short sentence: what is the driving goal/pressure of this session?

2) REQUIRED INGREDIENTS (2–4 lines)
- Location(s): [name them] — 1 short line: how the location matters this session.
- NPCs: [name them] — 1 short line: what role they play this session.

3) HOOK → BEATS (6–10 beats)
- Provide 6–10 beats.
- Each beat: 1–2 short sentences + (optional) one short half-sentence.
- Format each beat like this:
  Beat X: ...
  - Option A: ...   (ONLY include options for 2–3 beats total; you choose which beats)
  - Option B: ...
- Checks/mechanics: ONLY for 2–3 beats total, add at the end of the beat line:
  "Optional: [Check/Mechanik]" (e.g., "Optional: Insight", "Optional: Stealth", "Optional: Social leverage")
- Every beat must clearly connect to either a selected location detail or a selected NPC action/presence.

4) NPC FOCUS (max 4 NPCs; prefer selected + dominant from summary)
For each NPC (max 3 lines):
- Wants: ...
- Leverage: ...
- Next move (this session): ...

5) GM NOTES (max 5 bullets)
- Ultra-short reminders: pacing, a twist (optional), what to emphasize, what to cut if time runs short.
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

HARD REQUIREMENTS
- Respond entirely in German.
- Keep the EXACT same headings, ordering, and constraints as the V2 output format.
- Still produce exactly ONE scenario (no alternatives).
- Keep it concise, concrete, and table-usable. No prose, no metaphors.
- Ensure selected NPCs/locations are actively used; each selected NPC must have at least one explicit action beat.

OUTPUT FORMAT (strict)
Use the exact same section headings and structure as in the previous V2 output.
""".strip()
