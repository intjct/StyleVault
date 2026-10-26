import os

from sample_card import CARD, card
from stylevault import library as L, stylecard as SC


def test_plan_example_is_valid():
    assert SC.validate(CARD) == []
    assert SC.validate({"schema": 1, "name_th": "x", "tags": ["a"]}) == []          # minimal card is fine


def test_wrong_shapes_are_reported_not_raised():
    for bad in (None, [], "text", {}, card(schema=2), card(name_th=""), card(tags=[]), card(tags=list("abcdef")),
                card(tags="เร็ว"), card(visual="x"), card(pacing={"avg_shot_sec": "fast"}),
                card(audio={"sfx_th": [{"type_th": "x"}]}), card(structure=[{"from": "a", "to": 3}]),
                card(remotion_recipe={"fps": "30"}), card(fit_for_th="คำคม")):
        assert SC.validate(bad), bad


def test_thai_names_for_recipe_choices():
    assert SC.thai_choice("word-pop | typewriter", SC.TEXT_ANIM_TH) == "คำเด้งขึ้นทีละคำ / พิมพ์ดีดทีละตัว"
    assert SC.thai_choice("zoom-punch", SC.TRANSITION_TH) == "ซูมกระแทก"
    assert SC.thai_choice("something-new", SC.TRANSITION_TH) == "something-new"
    assert SC.thai_choice(None, SC.TRANSITION_TH) == ""


def test_library_only_returns_valid_cards(tmp_path):
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("tiktok", "1", "effects", "https://x")
    path = os.path.join(lib.clip_dir(cid), "style-card.json")
    L.write_json(path, CARD)
    assert lib.style_card(cid)["name_th"] == CARD["name_th"]
    L.write_json(path, card(tags=[]))
    assert lib.style_card(cid) is None
