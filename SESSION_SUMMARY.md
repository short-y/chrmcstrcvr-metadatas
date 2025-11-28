# Session Summary: Chromecast Radio Receiver (v5.17)

**Current Goal:**
We are building a custom Chromecast Receiver App (hosted on GitHub Pages) and a Python Sender script to play internet radio streams on a Google Nest Hub, displaying "Now Playing" metadata (Song Title/Artist/Album/Time) and album art that updates in real-time.

**Current Status:**
**All source code changes have been included and are up to date.**
- **Web App (`webapp.html`):**
    - **NEW:** Added Station Name display ("KOZT - The Coast").
    - **Features:** Polls KOZT API for metadata (Title, Artist, Album, Time, Art), applies local time conversion, and displays a live clock. No audio playback.
    - **Updates:** Metadata polling interval is randomized (10-25s) and **pauses when tab is hidden** to save resources.
- **Sender (`play_kozt.py` - New!):** 
    - **NEW:** Created a dedicated KOZT sender script based on v2.
    - **FIX:** Replaced deprecated `discover_chromecasts` with direct `CastBrowser` usage to silence warnings and ensure future compatibility.
    - **Defaults:** Hardcoded KOZT stream URL and App ID (`6509B35C`) for easier launching.
    - **Features:**
        - **Station Name Support:** Sends the station name (default: "KOZT - The Coast") to the receiver.
        - **No-Stream Mode (`--no-stream` or `-ns`):** Launches the receiver and updates metadata without playing audio.
- **Receiver (`index.html` / `receiver.html` - v5.17):** 
    - **WORKING:** Displays custom UI correctly and stays awake.
    - **New UI Element:** Added **Station Name** display above the album art.
    - **Updates:** `updateUI` function now accepts `stationName` parameter.
    - **Key Architecture:**
        - **Hidden `cast-media-player`:** Uses CSS Variables (`--logo-image: none`, etc.) and Shadow DOM Style Injection to make the default player invisible, while keeping it active off-screen.
    - **Features:**
        - **Time Zone Conversion:** Converts ISO 8601 timestamps and station time strings to local device time.
        - **Ambient Mode Prevention:** Implemented `maxInactivity=3600`, hidden player, and 30s heartbeat.

**History of "Ambient Mode" Fixes:**
1.  `disableIdleTimeout: true` in JS: Necessary but insufficient on its own for Nest Hubs.
2.  "Silent Video Hack" (1x1 pixel loop): Tried, but it interfered with the audio player UI updates.
3.  **Final Solution:** Using the standard `<cast-media-player>` (hidden by CSS opacity) allows the audio stream to drive the `PLAYING` state naturally, satisfying the OS requirements to keep the screen awake.

**Repo Info:**
- Working Directory: `/home/tsumrall/git/Chromecast`
- Remote Repo: `https://github.com/short-y/chrmcstrcvr-metadatas.git`
- Receiver URL: `https://short-y.github.io/chrmcstrcvr-metadatas/index.html`
- Web App URL: `https://short-y.github.io/chrmcstrcvr-metadatas/webapp.html`

**Commands to Resume:**
1.  Activate venv: `source venv/bin/activate`
2.  Run KOZT Sender: `python3 play_kozt.py "Office nest hub" -ns` (No-stream mode) or just `python3 play_kozt.py "Office nest hub"`