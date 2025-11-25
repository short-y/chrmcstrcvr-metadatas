# Session Summary: Chromecast Radio Receiver Debugging (v2.1 - KOZT Flag)

**Current Goal:**
We are building a custom Chromecast Receiver App (hosted on GitHub Pages) and a Python Sender script to play internet radio streams on a Google Nest Hub, displaying "Now Playing" metadata (Song Title/Artist) and album art that updates in real-time.

**Current Status:**
- **Sender (`play_radio_stream_v2.py`):** 
    - **UPDATED (v2.1):** Added `--kozt` command-line flag. If this flag is present, the script will explicitly use the Amperwave JSON API for KOZT metadata, regardless of the stream URL. This addresses the case where a KOZT stream URL might not contain "kozt" in its name.
    - **Metadata Source:**
        - For KOZT: Uses `https://api-nowplaying.amperwave.net/api/v1/prtplus/nowplaying/10/4756/nowplaying.json` to fetch `title`, `artist`, and `largeimage`.
        - For other streams: Uses original Icecast interleaved metadata.
    - **Album Art:** For KOZT, uses the `largeimage` URL directly from the Amperwave API. For generic Icecast streams, it uses the iTunes Search API as a fallback.
- **Receiver (`index.html` / `receiver.html`):** 
    - **STATUS:** v4.0 (Final cleanup). Displays custom UI correctly with track title, artist, and album art.

**Next Steps:**
1.  **Test with `--kozt` flag:** Run the V2 script with the new `--kozt` flag if the URL does not contain "kozt".

**Repo Info:**
- URL: `https://short-y.github.io/chrmcstrcvr-metadatas/index.html`

**Commands to Resume:**
1.  Activate venv: `source venv/bin/activate`
2.  Run V2 Sender (KOZT with flag): `python3 play_radio_stream_v2.py "Office nest hub" --url "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u" --app_id "6509B35C" --kozt`
3.  Run V2 Sender (Generic, if applicable): `python3 play_radio_stream_v2.py "Office nest hub" --url "YOUR_GENERIC_STREAM_URL" --app_id "YOUR_APP_ID"`
