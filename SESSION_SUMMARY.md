# Session Summary: Chromecast Radio Receiver (v5.7)

**Current Goal:**
We are building a custom Chromecast Receiver App (hosted on GitHub Pages) and a Python Sender script to play internet radio streams on a Google Nest Hub, displaying "Now Playing" metadata (Song Title/Artist/Album/Time) and album art that updates in real-time.

**Current Status:**
- **Sender (`play_radio_stream_v2.py` - v2.4):** 
    - **WORKING:** Fully functional and robust (Fixed `play_media` argument).
    - **Features:**
        - **KOZT-Specific Metadata:** Fetches title, artist, album, time, and `largeimage` (album art) directly from Amperwave JSON API, and includes album and time in the initial media load.
        - **Generic Stream Metadata:** Uses Icecast interleaved metadata for non-KOZT streams.
        - **Ping/Pong Keepalive:** Sends `PING` every 10s. Waits for `PONG`. If timeout/failure 3 times, assumes disconnect.
        - **Background Detection:** Checks `visibilityState` in `PONG` response. If `hidden`, attempts to re-foreground the app using `launch_app(app_id)` without stopping playback.
        - **Graceful Exit:** Handles `DISCONNECT` message from receiver (on `beforeunload`) to trigger immediate restart.
- **Receiver (`index.html` / `receiver.html` - v5.7):** 
    - **WORKING:** Displays custom UI correctly and stays awake.
    - **Key Architecture:**
        - **Removed `cast-media-player`:** We have removed the `<cast-media-player>` element entirely to force the display of our custom UI.
    - **Features:**
        - **Ambient Mode Prevention:** Implemented `maxInactivity=3600` and a 30s heartbeat that reloads a hidden 1x1 pixel image to ensure the Chromecast detects activity.

**History of "Ambient Mode" Fixes:**
1.  `disableIdleTimeout: true` in JS: Necessary but insufficient on its own for Nest Hubs.
2.  "Silent Video Hack" (1x1 pixel loop): Tried, but it interfered with the audio player UI updates.
3.  **Final Solution:** Using the standard `<cast-media-player>` (hidden by CSS opacity) allows the audio stream to drive the `PLAYING` state naturally, satisfying the OS requirements to keep the screen awake.

**Repo Info:**
- Working Directory: `/home/tsumrall/git/Chromecast`
- Remote Repo: `https://github.com/short-y/chrmcstrcvr-metadatas.git`
- GitHub Pages URL: `https://short-y.github.io/chrmcstrcvr-metadatas/index.html`

**Commands to Resume:**
1.  Activate venv: `source venv/bin/activate`
2.  Run V2 Sender (KOZT with flag): `python3 play_radio_stream_v2.py "Office nest hub" --url "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u" --app_id "6509B35C" --kozt --debug`
