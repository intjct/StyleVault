"""style-card.json: the file Claude writes. StyleVault only reads it — and never trusts it blindly:
a card with the wrong shape is reported as "unreadable" instead of crashing the screen."""
from __future__ import annotations

SCHEMA = 1


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def validate(card) -> list[str]:
    """Returns a list of problems; an empty list means the card is safe to show."""
    if not isinstance(card, dict):
        return ["not an object"]
    bad: list[str] = []
    if card.get("schema") != SCHEMA:
        bad.append("schema must be 1")
    if not (isinstance(card.get("name_th"), str) and card["name_th"].strip()):
        bad.append("name_th missing")
    tags = card.get("tags")
    if not (_str_list(tags) and 1 <= len(tags) <= 5):
        bad.append("tags must be 1-5 strings")
    for key in ("summary_th", "analyzed_at", "analyzed_by", "engky_fit_th"):
        if card.get(key) is not None and not isinstance(card[key], str):
            bad.append(f"{key} must be text")
    for key in ("fit_for_th", "limits_th"):
        if card.get(key) is not None and not _str_list(card[key]):
            bad.append(f"{key} must be a list of text")
    for key in ("visual", "pacing", "audio", "remotion_recipe"):
        if card.get(key) is not None and not isinstance(card[key], dict):
            bad.append(f"{key} must be an object")
    vis = card.get("visual") if isinstance(card.get("visual"), dict) else {}
    if vis.get("palette") is not None and not _str_list(vis["palette"]):
        bad.append("visual.palette must be a list of colors")
    for k in ("look_th", "text_style_th", "layout_th"):
        if vis.get(k) is not None and not isinstance(vis[k], str):
            bad.append(f"visual.{k} must be text")
    pac = card.get("pacing") if isinstance(card.get("pacing"), dict) else {}
    if pac.get("avg_shot_sec") is not None and not _is_num(pac["avg_shot_sec"]):
        bad.append("pacing.avg_shot_sec must be a number")
    if pac.get("transitions_th") is not None and not _str_list(pac["transitions_th"]):
        bad.append("pacing.transitions_th must be a list of text")
    aud = card.get("audio") if isinstance(card.get("audio"), dict) else {}
    sfx = aud.get("sfx_th")
    if sfx is not None and not (isinstance(sfx, list) and all(isinstance(x, dict) and _is_num(x.get("t")) for x in sfx)):
        bad.append("audio.sfx_th must be a list of {t, type_th, role_th}")
    st = card.get("structure")
    if st is not None and not (isinstance(st, list) and all(
            isinstance(x, dict) and _is_num(x.get("from")) and _is_num(x.get("to")) for x in st)):
        bad.append("structure must be a list of {from, to, beat_th}")
    rec = card.get("remotion_recipe") if isinstance(card.get("remotion_recipe"), dict) else {}
    for k in ("fps", "shot_frames"):
        if rec.get(k) is not None and not _is_num(rec[k]):
            bad.append(f"remotion_recipe.{k} must be a number")
    return bad


TEXT_ANIM_TH = {"word-pop": "คำเด้งขึ้นทีละคำ", "line-slide-up": "ทั้งบรรทัดสไลด์ขึ้น", "typewriter": "พิมพ์ดีดทีละตัว"}
TRANSITION_TH = {"fade": "จางเข้า-ออก", "slide": "สไลด์", "zoom-punch": "ซูมกระแทก", "whip": "ปัดเร็ว"}


def thai_choice(value, table: dict) -> str:
    """'word-pop | typewriter' -> 'คำเด้งขึ้นทีละคำ / พิมพ์ดีดทีละตัว' (unknown words are kept as they are)."""
    if not isinstance(value, str) or not value.strip():
        return ""
    parts = [p.strip() for p in value.replace(",", "|").split("|") if p.strip()]
    return " / ".join(table.get(p, p) for p in parts)


def mmss(sec) -> str:
    sec = float(sec)
    return f"{int(sec // 60)}:{sec % 60:05.2f}"
