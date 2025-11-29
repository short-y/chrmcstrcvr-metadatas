# Project-Specific Instructions for Chromecast Repository

This `GEMINI.md` file contains instructions and conventions specifically for the `/home/tsumrall/git/Chromecast` project.

## General Guidelines:

*   **`index.html` & `receiver.html` Synchronization**: `receiver.html` must always be an exact copy of `index.html`. When `index.html` is modified, `receiver.html` must also be updated to match.
*   **Version Numbering**: Always increment the version number in both `index.html` and `receiver.html` when making changes. Version strings should exclude "Stable" and "Robust" labels (e.g., use "v5.2" instead of "v5.2 (Stable)").
*   **`play_radio_stream_v2.py` Behavior**: This script pre-fetches KOZT metadata before starting playback to ensure the correct UI is displayed immediately, replacing the default "Radio Paradise" placeholder.