import os

from stylevault import library as L


def test_url_checks():
    assert L.looks_like_url("https://www.tiktok.com/@x/video/7412345")
    assert L.looks_like_url("tiktok.com/@x/video/1")
    assert not L.looks_like_url("สวัสดี ไม่ใช่ลิงก์")
    assert not L.looks_like_url("hello")


def test_platforms_and_ids():
    assert L.platform_of("https://vm.tiktok.com/abc/") == "tiktok"
    assert L.platform_of("https://www.youtube.com/shorts/AbCdEf12345") == "youtube"
    assert L.platform_of("https://youtu.be/AbCdEf12345") == "youtube"
    assert L.platform_of("https://www.instagram.com/reel/Cxyz1/") == "instagram"
    assert L.platform_of("https://fb.watch/xyz/") == "facebook"
    assert L.platform_of("https://example.com/a") is None
    assert L.short_id_of("https://www.tiktok.com/@x/video/7412345?lang=th", "tiktok") == "7412345"
    assert L.short_id_of("https://www.youtube.com/shorts/AbCdEf12345", "youtube") == "AbCdEf12345"
    assert L.short_id_of("https://www.instagram.com/reel/Cxyz1/", "instagram") == "Cxyz1"
    a = L.short_id_of("https://example.com/a", "other")
    assert a == L.short_id_of("https://example.com/a", "other") and len(a) == 8


def test_view_format():
    assert L.fmt_views(1_400_000) == "1.4M"
    assert L.fmt_views(850_000) == "850K"
    assert L.fmt_views(12_300) == "12.3K"
    assert L.fmt_views(999) == "999"
    assert L.fmt_views(None) == ""


def test_create_list_index_delete(tmp_path):
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("tiktok", "7412345", "viral", "https://x/y")
    assert cid.endswith("_tiktok_7412345")
    assert lib.find_existing("tiktok", "7412345") == cid
    assert lib.meta(cid)["status"] == "downloading"
    lib.update_meta(cid, status="waiting", view_count=5)
    lib.rebuild_index()
    idx = L.read_json(str(tmp_path / "lib" / "library-index.json"))
    assert idx["clips"][0]["id"] == cid and idx["clips"][0]["view_count"] == 5
    # style-card.json belongs to Claude: the program only reads it
    card = {"schema": 1, "name_th": "ทดสอบ", "tags": ["เร็ว"]}
    L.write_json(os.path.join(lib.clip_dir(cid), "style-card.json"), card)
    lib.rebuild_index()
    assert L.read_json(str(tmp_path / "lib" / "library-index.json"))["clips"][0]["name_th"] == "ทดสอบ"
    lib.delete_clip(cid)
    assert lib.list_ids() == []


def test_broken_json_does_not_crash(tmp_path):
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("tiktok", "1", "effects", "https://x")
    with open(os.path.join(lib.clip_dir(cid), "style-card.json"), "w") as f:
        f.write("{ not json")
    assert lib.style_card(cid) is None
    lib.rebuild_index()
