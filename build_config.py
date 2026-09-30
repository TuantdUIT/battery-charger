"""Ghi config.js chứa GOONG_MAP_KEY (lấy bằng os.getenv từ .env) cho map_hcm.html."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    # Không có python-dotenv: nạp thủ công các dòng KEY=VALUE vào os.environ
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

key = os.getenv("GOONG_MAP_KEY")
if not key:
    raise SystemExit("Không tìm thấy GOONG_MAP_KEY trong .env")

(ROOT / "config.js").write_text(
    "window.GOONG_MAP_KEY = " + json.dumps(key) + ";\n", encoding="utf-8"
)
print("Wrote config.js")
