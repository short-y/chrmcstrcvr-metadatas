# Session Summary: Chromecast Radio Receiver Debugging (v3.5)

**Current Goal:**
We are building a custom Chromecast Receiver App (hosted on GitHub Pages) and a Python Sender script to play internet radio streams on a Google Nest Hub. The key challenge is displaying "Now Playing" metadata (Song Title/Artist) that updates in real-time.

**Current Status:**
- **Sender (`play_radio_stream.py`):** WORKING (Fixed a bug with duplicate main block).
- **Receiver (`index.html` / `receiver.html`):** 
    - **ISSUE:** User reports "momentary display with the red boxes but it then changes to a different screen" when playback starts.
    - **Hypothesis:** The `cast-media-player` element, despite `opacity: 0`, might be overlaying the content or triggering a native "Now Playing" view on the Nest Hub because it's part of the active render tree.
    - **Fix Attempt (v3.5):** 
        - Wrapped `<cast-media-player>` in a `div` with `#player-hidden-wrapper`.
        - Set this wrapper to `visibility: hidden`, `position: absolute`, `z-index: -1000`, `width: 1px`, `height: 1px`.
        - This ensures the player is "present" in the DOM (so CAF works) but completely removed from the visual rendering path of the page's main layout.

**Next Steps for Future Session:**
1.  **Check Visuals (v3.5):**
    - If the "different screen" persists, it might be the **Touch Controls** overlay or **Google Assistant Media** view which operates outside the Web Receiver's DOM.
    - If fixed, the custom UI (lime green text) should stay visible.
2.  **Repo Info:**
    - URL: `https://short-y.github.io/chrmcstrcvr-metadatas/index.html`

**Commands to Resume:**
1.  Activate venv: `source venv/bin/activate`
2.  Run Sender: `python3 play_radio_stream.py "Office nest hub" --url "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u" --app_id "6509B35C"`