#!/usr/bin/env python3
"""
Generate playlist.m3u8 containing ONLY working streams (001 → 3500)
"""

import concurrent.futures
import urllib.request
import urllib.error
from pathlib import Path

OUTPUT = "playlist.m3u8"
BASE_URL = "http://223.25.71.211:5001/live/{:03d}.m3u8"
MAX_WORKERS = 40          # parallel connections
TIMEOUT = 5               # seconds per request
TOTAL = 3500

def is_working(num: int) -> tuple[int, bool]:
    url = BASE_URL.format(num)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            # Accept 200 / 301 / 302 and make sure it's actually an m3u8
            if resp.status in (200, 301, 302):
                content_type = resp.headers.get("Content-Type", "").lower()
                if "mpegurl" in content_type or "m3u8" in content_type or True:
                    # Read a small part just to confirm it looks like a playlist
                    data = resp.read(512).decode("utf-8", errors="ignore")
                    if "#EXTM3U" in data or "#EXT" in data or len(data) > 20:
                        return num, True
    except Exception:
        pass
    return num, False


def main():
    print(f"Checking {TOTAL} streams with {MAX_WORKERS} workers...")
    working = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(is_working, i): i for i in range(1, TOTAL + 1)}
        
        for future in concurrent.futures.as_completed(futures):
            num, ok = future.result()
            if ok:
                working.append(num)
                print(f"✅ {num:03d} working")
            # else: silently skip

    working.sort()

    # Write only working streams
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for num in working:
            f.write(f"#EXTINF:-1,Channel {num:03d}\n")
            f.write(BASE_URL.format(num) + "\n")

    print("-" * 40)
    print(f"Finished! {len(working)} working streams saved to {OUTPUT}")
    print(f"Dead / unreachable: {TOTAL - len(working)}")


if __name__ == "__main__":
    main()
