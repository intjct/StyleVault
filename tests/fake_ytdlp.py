"""Stand-in for yt-dlp used by the tests: answers -J with JSON, and "downloads" a generated video."""
import json
import os
import subprocess
import sys

args = sys.argv[1:]
url = args[-1]
if "--cookies-from-browser" in args and "COOKIEBAD" in url:
    sys.stderr.write("ERROR: Could not copy Chrome cookie database. See  https://github.com/yt-dlp/yt-dlp/issues/7271\n")
    sys.exit(1)
if "FAIL" in url:
    sys.stderr.write("ERROR: [tiktok] 1: This video is private. Log in to view\n")
    sys.exit(1)
if "-J" in args:
    print(json.dumps({"id": "7412345", "title": "คลิปทดสอบ", "uploader": "@tester", "upload_date": "20260921",
                      "view_count": 1400000, "like_count": 220000, "duration": 2.0}))
    sys.exit(0)
tmpl = args[args.index("-o") + 1].replace("%(ext)s", "mp4")
for pct in ("10.0", "55.5", "100.0"):
    print(f"[download]  {pct}% of 1.00MiB", flush=True)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=30:duration=2",
                "-pix_fmt", "yuv420p", tmpl], check=True)
