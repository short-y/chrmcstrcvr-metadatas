# Session Summary: Chromecast Radio Receiver (v2.2 - Finalized)

**Current Goal:**
We are building a custom Chromecast Receiver App (hosted on GitHub Pages) and a Python Sender script to play internet radio streams on a Google Nest Hub, displaying "Now Playing" metadata (Song Title/Artist/Album/Time) and album art that updates in real-time.

**Current Status:**
- **Sender (`play_radio_stream_v2.py` - v2.2):** 
    - **WORKING:** Fully functional and robust.
    - **Features:**
        - **KOZT-Specific Metadata:** Fetches title, artist, album, time, and `largeimage` (album art) directly from Amperwave JSON API (`https://api-nowplaying.amperwave.net/api/v1/prtplus/nowplaying/10/4756/nowplaying.json`) for KOZT streams.
        - **Generic Stream Metadata:** Uses Icecast interleaved metadata for non-KOZT streams, falling back to iTunes Search API for album art.
        - **`--kozt` flag:** Explicitly forces KOZT metadata mode, even if the stream URL doesn't contain "kozt".
        - **Auto-reconnection:** Detects Chromecast disconnection or app exit, and automatically attempts to relaunch the app and resume monitoring.
        - **Graceful Exit:** Handles `Ctrl+C` (`KeyboardInterrupt`) cleanly to stop the script without restarting.
        - **Configurable Debugging:** Verbose debug messages are now hidden by default and enabled only when the `--debug` flag is used.
- **Receiver (`index.html` / `receiver.html` - v4.1):** 
    - **WORKING:** Displays custom UI correctly with track title, artist, album name, track time, and album art.
    - **Fixes Applied:**
        1.  **Viewport Meta Tag:** Added `<meta name="viewport" ...>` for proper scaling on Nest Hub.
        2.  **Responsive CSS:** Used `vw` and `vh` units for font sizes and element dimensions.
        3.  **Removed `cast-media-player`:** The element that caused the default player UI to appear has been removed entirely, as per CAF documentation for custom UIs.
        4.  **`touchScreenOptimizedApp`:** Enabled this option in `CastReceiverOptions` to explicitly signal custom touch handling.
        5.  **`disableIdleTimeout`:** Enabled to prevent the app from closing prematurely.
        6.  **New Metadata Fields:** Added display for Album Name and Track Time.

**Next Steps for Future Session:**
- The core functionality is robust and working. Further enhancements would be new feature requests.

**Repo Info:**
- Working Directory: `/home/tsumrall/git/Chromecast` (which tracks the `chrmcstrcvr-metadatas` repo).
- Remote Repo: `https://github.com/short-y/chrmcstrcvr-metadatas.git`
- GitHub Pages URL: `https://short-y.github.io/chrmcstrcvr-metadatas/index.html`

**Commands to Resume:**
1.  Activate venv: `source venv/bin/activate`
2.  Run V2 Sender (KOZT with flag): `python3 play_radio_stream_v2.py "Office nest hub" --url "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u" --app_id "6509B35C" --kozt`
3.  Run V2 Sender (Generic, if applicable): `python3 play_radio_stream_v2.py "Office nest hub" --url "YOUR_GENERIC_STREAM_URL" --app_id "YOUR_APP_ID"`