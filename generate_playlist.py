#!/usr/bin/env python3
"""
Generate playlist.m3u8 with ONLY working streams.
Extracts channel name from m3u8 when available, otherwise uses "Channel XXX".
Sorted alphabetically by name.
"""

import concurrent.futures
import re
import urllib.request

OUTPUT = "playlist.m3u8"
BASE_URL = "http://223.25.71.211:5001/live/{:03d}.m3u8"
MAX_WORKERS = 40
TIMEOUT = 6
TOTAL = 5500


def extract_name(content: str, fallback: str) -> str:
    """Try to extract a clean channel name from m3u8 content."""
    patterns = [
        r'#EXTINF:[^,]*,\s*(.+)',          # #EXTINF:-1,Name
        r'tvg-name="([^"]+)"',             # tvg-name="Name"
        r'tvg-id="([^"]+)"',               # tvg-id="Name"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\[.*?\]', '', name)      # remove [HD], [4K] etc.
            name = re.sub(r'\s+', ' ', name).strip()
            if name and len(name) > 1:
                return name
    return fallback


def check_stream(num: int) -> tuple[str, str] | None:
    """Returns (name, url) if the stream is working."""
    url = BASE_URL.format(num)
    fallback = f"Channel {num:03d}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status not in (200, 301, 302):
                return None

            data = resp.read(2048).decode("utf-8", errors="ignore")

            # Basic check that it looks like a playlist
            if "#EXT" not in data and len(data) < 30:
                return None

            name = extract_name(data, fallback)
            return name, url

    except Exception:
        return None


def main():
    print(f"Checking {TOTAL} streams with {MAX_WORKERS} workers...")
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_stream, i) for i in range(1, TOTAL + 1)]
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                name, url = result
                results.append((name, url))
                print(f"✅ {name}")

    # Sort alphabetically by channel name
    results.sort(key=lambda x: x[0].lower())

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, url in results:
            f.write(f"#EXTINF:-1,{name}\n")
            f.write(f"{url}\n")

    print("-" * 50)
    print(f"Finished! {len(results)} working channels saved to {OUTPUT}")


if __name__ == "__main__":
    main()
