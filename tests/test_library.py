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


def test_clip_numbers_follow_add_order_and_are_never_reused(tmp_path):
    lib = L.Library(str(tmp_path / "lib"))
    a = lib.create_clip("tiktok", "111", "effects", "https://x")
    b = lib.create_clip("youtube", "222222", "viral", "https://y")
    c = lib.create_clip("file", "abc", "effects", None)
    assert [lib.number_of(i) for i in (a, b, c)] == [1, 2, 3]
    lib.delete_clip(b)
    d = lib.create_clip("instagram", "dddd", "viral", "https://z")
    assert lib.number_of(d) == 4                       # #2 is not handed out again
    lib.delete_clip(d)                                  # the newest one is gone ...
    assert lib.create_clip("facebook", "555", "viral", "https://f") and \
        lib.number_of(lib.find_existing("facebook", "555")) == 5   # ... and #4 still is not reused
    idx = L.read_json(os.path.join(lib.root, "library-index.json"))
    lib.rebuild_index()
    idx = L.read_json(os.path.join(lib.root, "library-index.json"))
    assert sorted(x["number"] for x in idx["clips"]) == [1, 3, 5]
    assert L.num_label({"number": 7}) == "#7" and L.num_label({}) == "" and L.num_label(None) == ""


def test_adding_same_clip_again_keeps_its_number(tmp_path):
    lib = L.Library(str(tmp_path / "lib"))
    a = lib.create_clip("tiktok", "111", "effects", "https://x")
    lib.create_clip("youtube", "222222", "viral", "https://y")
    assert lib.create_clip("tiktok", "111", "effects", "https://x") == a
    assert lib.number_of(a) == 1


def test_old_clips_get_numbers_by_added_time(tmp_path):
    root = tmp_path / "lib"
    for cid, when in (("2026-10-26_tiktok_b", "2026-10-26T10:00:00+07:00"),
                      ("2026-10-25_tiktok_a", "2026-10-25T10:00:00+07:00"),
                      ("2026-10-27_tiktok_c", "2026-10-27T10:00:00+07:00")):
        d = root / "clips" / cid
        d.mkdir(parents=True)
        L.write_json(str(d / "meta.json"), {"id": cid, "added_at": when, "status": "waiting"})
    lib = L.Library(str(root))                          # opening an old library numbers it
    assert [lib.number_of(i) for i in ("2026-10-25_tiktok_a", "2026-10-26_tiktok_b", "2026-10-27_tiktok_c")] == [1, 2, 3]
    assert L.Library(str(root)).number_of("2026-10-25_tiktok_a") == 1     # opening again changes nothing
    e = lib.create_clip("youtube", "eeeeee", "viral", None)
    assert lib.number_of(e) == 4


def test_lost_counter_file_never_reuses_a_number_on_disk(tmp_path):
    lib = L.Library(str(tmp_path / "lib"))
    lib.create_clip("tiktok", "111", "effects", None)
    lib.create_clip("tiktok", "222", "effects", None)
    os.remove(lib._counter_path())
    assert lib.number_of(lib.create_clip("tiktok", "333", "effects", None)) == 3
