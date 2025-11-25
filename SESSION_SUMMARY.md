# Session Summary: Chromecast Radio Receiver Debugging (v3.6)

**Current Goal:**
We are building a custom Chromecast Receiver App (hosted on GitHub Pages) and a Python Sender script to play internet radio streams on a Google Nest Hub. The key challenge is displaying "Now Playing" metadata (Song Title/Artist) that updates in real-time.

**Current Status:**
- **Sender (`play_radio_stream.py`):** 
    - **FIXED:** Duplicate main block.
    - **UPDATED (v3.6):** Added logic to verify the active App ID after launch. It now waits 2 seconds and warns if the running App ID doesn't match the requested one. This helps confirm if the device is silently falling back to the Default Media Receiver.
- **Receiver (`index.html` / `receiver.html`):** 
    - **Status:** v3.5 deployed (Player Hidden Wrapper).
    - **Issue:** User still sees "regular cast screen". This strongly implies the Custom Receiver isn't running at all.

**Debugging Hypothesis:**
The "regular cast screen" is the **Default Media Receiver**. The custom App ID launch is likely failing silently or being overridden, causing `pychromecast` (or the device) to fall back. The new checks in `play_radio_stream.py` will confirm this.

**Next Steps:**
1.  **Run Updated Sender:** User should run the v3.6 sender script.
2.  **Check Output:** Look for the warning: `WARNING: Active App ID (...) does not match requested ID (...)`.
    - **If Warning Appears:** The issue is Registration/Propagation. The App ID is invalid, the device isn't registered for dev, or the serial number hasn't propagated.
    - **If NO Warning:** The Custom App *is* running, but the "regular screen" means our `index.html` is either failing to load (404/Certificate Error) or the default player is somehow still visible despite our CSS.

**Commands to Resume:**
1.  Activate venv: `source venv/bin/activate`
2.  Run Sender: `python3 play_radio_stream.py "Office nest hub" --url "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u" --app_id "6509B35C"`
