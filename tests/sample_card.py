"""The example style card from the plan (section 4.4), used by the tests."""
import copy

CARD = {
    "schema": 1,
    "analyzed_at": "2026-10-26T22:30:00+07:00",
    "analyzed_by": "claude-sonnet-5",
    "name_th": "การ์ดคำคมคนดัง จังหวะเร็ว",
    "summary_th": "การ์ดกระดาษลอยบนพื้นเทา ข้อความขึ้นทีละท่อน คำเน้นสีม่วง ตัดเร็วทุก 1.6 วินาที",
    "tags": ["เร็ว", "ไวรัล", "เสียงวูบ"],
    "fit_for_th": ["คลิปคำคม", "สรุปประวัติบุคคล"],
    "visual": {"palette": ["#F2F2F2", "#7A2E8E"], "look_th": "ขาวเทาสะอาด เน้นม่วง",
               "text_style_th": "ตัวหนา ขึ้นทีละคำ", "layout_th": "ข้อความกลางจอ การ์ดลอย"},
    "pacing": {"avg_shot_sec": 1.6, "feel_th": "เร็วมาก", "transitions_th": ["สไลด์ขึ้น", "ซูมกระแทก"]},
    "audio": {"music_th": "เพลงจังหวะเร็ว ไม่มีช่วงเงียบ", "voice_th": "ไม่มีเสียงพูด",
              "sfx_th": [{"t": 0.38, "type_th": "เสียงวูบ", "role_th": "นำก่อนภาพเปลี่ยน"}]},
    "structure": [{"from": 0, "to": 3, "beat_th": "ฮุก: คำคมใหญ่เต็มจอ"}, {"from": 3, "to": 10, "beat_th": "เนื้อ: ประวัติ"}],
    "remotion_recipe": {"fps": 30, "shot_frames": 48, "text_anim": "word-pop | typewriter", "transition": "zoom-punch",
                        "sfx_rule_th": "ใส่เสียงวูบ 3 เฟรมก่อนทุกจุดตัด", "notes_th": "คำเน้นใช้สีม่วง"},
    "engky_fit_th": None,
    "limits_th": ["ชื่อฟอนต์จริงระบุไม่ได้"],
}


def card(**over):
    c = copy.deepcopy(CARD)
    c.update(over)
    return c
