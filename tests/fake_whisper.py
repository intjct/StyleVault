"""Stand-in for whisper-cli used by the tests: writes <-of>.json like whisper.cpp -oj does."""
import json
import sys

a = sys.argv[1:]
if "-h" in a:
    print("usage: whisper-cli [options] file0 file1 ...")
    sys.exit(0)
base = a[a.index("-of") + 1]
assert a[a.index("-f") + 1].endswith(".wav")
json.dump({"result": {"language": "th"}, "transcription": [
    {"offsets": {"from": 0, "to": 1500}, "text": " สวัสดีครับ วันนี้มาดูเทคนิคตัดต่อ"},
    {"offsets": {"from": 1500, "to": 1800}, "text": " [Music]"},
    {"offsets": {"from": 1800, "to": 3000}, "text": " กดติดตามด้วยนะ"},
]}, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False)
