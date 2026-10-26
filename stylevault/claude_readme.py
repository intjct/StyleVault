"""CLAUDE-README.md — the short guide StyleVault leaves inside the library folder for Claude."""
from . import VERSION

TEXT = f"""<!-- StyleVault {VERSION} — โปรแกรมสร้างไฟล์นี้ให้ ห้ามแก้เอง (จะถูกเขียนทับเมื่อเปิดโปรแกรมเวอร์ชันใหม่) -->
# คู่มือสำหรับ Claude: คลังสไตล์ (StyleVault)

โฟลเดอร์นี้คือคลังคลิปตัวอย่างของแตม (เจ้าของ) ตอบเป็นภาษาไทย ใช้ตาราง และขั้นตอนเรียงเลขเส้นเดียว
คลิปทั้งหมดมีไว้ศึกษาเท่านั้น ห้ามนำไปโพสต์ซ้ำ

## โครงสร้าง
```
library-index.json        ← อ่านไฟล์นี้ก่อนเสมอ (สารบัญคลัง)
clips/<วันที่เพิ่ม>_<แพลตฟอร์ม>_<id>/
  video.mp4  thumb.jpg
  meta.json                ← โปรแกรมเขียน (Claude แก้ได้เฉพาะช่อง status)
  raw/                     ← โปรแกรมเขียน: ข้อมูลดิบที่วัดจากคลิปจริง
    cuts.json              จุดตัด (cuts_sec), ความเร็วเฉลี่ยต่อช็อต, motion_curve ทุก 0.5 วิ
    audio.json             ความดัง, ช่วงเงียบ, จุดเสียงกระแทก (onsets_sec), onsets_near_cut, bpm, sfx[]
    frames/                ภาพนิ่งตั้งชื่อ <ลำดับ>_<วินาที>s.jpg (ไม่เกิน 30 ภาพ)
    contact-sheet.jpg      ภาพรวมทั้งคลิปในภาพเดียว (ดูอันนี้ก่อน)
    waveform.png           รูปคลื่นเสียง
    sfx/                   ไฟล์เสียงสั้นรอบแต่ละจุดเสียงกระแทก (ชื่อ <ลำดับ>_<วินาที>s.wav)
    transcript.json        บทพูด (เวอร์ชันหลังๆ)
  style-card.json          ← Claude เขียนเท่านั้น (โปรแกรมไม่เขียนทับ)
  notes.md                 ← แตมเขียนเอง ให้น้ำหนักมากที่สุด
```
meta.json: `kind` = effects (สไตล์เอฟเฟกต์) หรือ viral (คลิปไวรัล) ; `status` = downloading | preparing | waiting (รอวิเคราะห์) | analyzed | error ;
`view_count` / `like_count` เป็น null ได้ ถ้าดึงไม่ได้

## เมื่อแตมพิมพ์ "วิเคราะห์คลิปใหม่"
1. อ่าน `library-index.json` หาคลิปที่ `status = waiting`
2. ต่อคลิป: อ่าน `meta.json`, `raw/cuts.json`, `raw/audio.json`, `notes.md` → ดู `raw/contact-sheet.jpg` ก่อน → ดูภาพใน `raw/frames/` เพิ่มเฉพาะช่วงที่จุดตัดถี่หรือสงสัย (ประหยัดโทเค็น)
3. เขียน `style-card.json` ตาม schema ด้านล่างเป๊ะ (ภาษาไทยทุกช่อง `_th`)
4. แก้ `meta.json` เฉพาะ `status` เป็น `"analyzed"`
5. ตอบแตมเป็นตารางสั้น: คลิป | ชื่อสไตล์ | แท็ก
6. ห้ามเขียนอะไรนอกโฟลเดอร์คลิปนั้น ห้ามลบไฟล์

กฎการวิเคราะห์: ตัวเลขทุกตัว (จุดตัด เวลาเสียง BPM) ต้องมาจากไฟล์ใน raw/ ไม่เดา ; สิ่งที่ดูจากภาพแล้วไม่แน่ใจให้ใส่ใน `limits_th` ;
ให้น้ำหนักกับ `notes.md` มากที่สุด ; `kind=viral` ต้องมี `structure` อย่างน้อย ฮุก/เนื้อ/ปิด ; `kind=effects` ต้องมี `remotion_recipe` ที่ทำซ้ำได้จริง
ข้อควรรู้: `onsets_sec` คือจุดที่เสียงดังพุ่งขึ้นกะทันหัน อาจเป็นเสียงเอฟเฟกต์หรือคำพูดก็ได้ ต้องฟัง `raw/sfx/` หรือดูบริบทภาพประกอบ

## schema ของ style-card.json
```json
{{
  "schema": 1,
  "analyzed_at": "2026-10-26T22:00:00+07:00",
  "analyzed_by": "claude-...",
  "name_th": "ชื่อสไตล์สั้นๆ",
  "summary_th": "1–2 ประโยค",
  "tags": ["แท็กหลัก", "แท็ก2"],
  "fit_for_th": ["เหมาะกับเนื้อหาแบบไหน"],
  "visual": {{ "palette": ["#F2F2F2"], "look_th": "", "text_style_th": "", "layout_th": "" }},
  "pacing": {{ "avg_shot_sec": 1.6, "feel_th": "", "transitions_th": [""] }},
  "audio": {{ "music_th": "", "sfx_th": [{{"t": 0.38, "type_th": "", "role_th": ""}}], "voice_th": "" }},
  "structure": [{{ "from": 0, "to": 3, "beat_th": "ฮุก: ..." }}],
  "remotion_recipe": {{ "fps": 30, "shot_frames": 48, "text_anim": "word-pop | line-slide-up | typewriter",
                       "transition": "fade | slide | zoom-punch | whip", "sfx_rule_th": "", "notes_th": "" }},
  "engky_fit_th": null,
  "limits_th": [""]
}}
```
`tags` ไม่เกิน 5 อัน แท็กแรกคือแท็กหลัก ; `engky_fit_th` ใส่ข้อความเฉพาะเมื่อเหมาะกับคลิปอิงกี้ที่ยังไม่ลงจริงๆ ไม่งั้น null

## เมื่อแตมสั่งตัดต่อด้วย Remotion / ทำคลิปเรื่องใหม่
1. อ่าน `library-index.json` เลือก 2–3 สไตล์ที่ `fit_for_th` ตรงกับเรื่อง
2. เสนอเป็นตาราง: สไตล์ | ทำไมเหมาะ | ยอดวิวคลิปต้นแบบ — ให้แตมเลือก
3. อ่าน `style-card.json` ของสไตล์ที่เลือก ใช้ `remotion_recipe` + `audio.sfx_th` ตัดต่อ
4. หลังส่งงาน ถ้าแตมคอมเมนต์ ให้ต่อท้าย `notes.md` ของสไตล์นั้นว่า "ใช้กับงาน X — แตมชอบ/ไม่ชอบ ..."
"""
