#!/usr/bin/env python3
"""
Generate playlist.m3u8 with only working streams.
Tries m3u8 text first, then ffprobe for channel name.
"""

import concurrent.futures
import re
import subprocess
import urllib.request
from pathlib import Path

OUTPUT = "playlist.m3u8"
BASE_URL = "http://223.25.71.211:5001/live/{:03d}.m3u8"
MAX_WORKERS = 25          # lower because ffprobe is heavier
TIMEOUT = 6
TOTAL = 3500
FFPROBE_TIMEOUT = 12      # seconds

def extract_name_from_m3u8(content: str) -> str | None:
    patterns = [
        r'#EXTINF:[^,]*,\s*(.+)',
        r'tvg-name="([^"]+)"',
        r'tvg-id="([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\[.*?\]', '', name)
            name = re.sub(r'\s+', ' ', name).strip()
            if name and len(name) > 2 and not name.lower().startswith("channel"):
                return name
    return None


def extract_name_from_ffprobe(url: str) -> str | None:
    """Use ffprobe to get service_name / title from the stream."""
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_entries", "program_tags=service_name:stream_tags=title",
            "-i", url
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT
        )
        if result.returncode != 0:
            return None

        # Simple text search in the JSON output (avoids needing json module parsing)
        for key in ["service_name", "title", "SERVICE_NAME"]:
            match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', result.stdout)
            if match:
                name = match.group(1).strip()
                if name and len(name) > 2:
                    return name
    except Exception:
        pass
    return None


def check_stream(num: int) -> tuple[str, str] | None:
    """Returns (name, url) if working."""
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
            if "#EXT" not in data and len(data) < 30:
                return None

            # 1. Try fast m3u8 parsing
            name = extract_name_from_m3u8(data)

            # 2. If no good name → try ffprobe
            if not name:
                name = extract_name_from_ffprobe(url)

            final_name = name if name else fallback
            return final_name, url

    except Exception:
        return None


def main():
    print(f"Checking {TOTAL} streams...")
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
    print(f"Done! {len(results)} working channels saved → {OUTPUT}")


if __name__ == "__main__":
    main()
