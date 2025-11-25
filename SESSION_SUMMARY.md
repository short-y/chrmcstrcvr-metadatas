# Session Summary: Chromecast Radio Receiver Debugging (v3.7)

**Current Goal:**
We are building a custom Chromecast Receiver App (hosted on GitHub Pages) and a Python Sender script to play internet radio streams on a Google Nest Hub. The key challenge is displaying "Now Playing" metadata (Song Title/Artist) that updates in real-time.

**Current Status:**
- **Sender (`play_radio_stream.py`):** WORKING (Verified App ID).
- **Receiver (`index.html` / `receiver.html`):** 
    - **ISSUE:** User reports text is "much smaller than usual" and looks like it's designed for a larger screen.
    - **Hypothesis:** The `viewport` meta tag was missing, causing the Nest Hub to render the page at a desktop resolution (e.g., 980px) and scale it down, making everything tiny.
    - **Fix (v3.7):** 
        - Added `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.
        - Updated CSS to use relative units (`vw`, `vh`) instead of fixed `px` or `em` for better scaling on small screens.
        - Song Title: `5vw`
        - Artist Name: `3vw`
        - Album Art: `30vw`

**Next Steps for Future Session:**
1.  **Check Visuals (v3.7):**
    - The layout should now fill the screen properly.
    - Text should be legible.
    - If text is *too* big now, we can dial back the `vw` values.
2.  **Repo Info:**
    - URL: `https://short-y.github.io/chrmcstrcvr-metadatas/index.html`

**Commands to Resume:**
1.  Activate venv: `source venv/bin/activate`
2.  Run Sender: `python3 play_radio_stream.py "Office nest hub" --url "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u" --app_id "6509B35C"`