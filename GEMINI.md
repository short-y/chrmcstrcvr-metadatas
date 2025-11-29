# Project-Specific Instructions for Chromecast Repository

This `GEMINI.md` file contains instructions and conventions specifically for the `/home/tsumrall/git/Chromecast` project.

## General Guidelines:

*   **`index.html` & `receiver.html` Synchronization**: `receiver.html` must always be an exact copy of `index.html`. When `index.html` is modified, `receiver.html` must also be updated to match.
*   **Version Numbering**: Always increment the version number in both `index.html` and `receiver.html` when making changes. Version strings should exclude "Stable" and "Robust" labels (e.g., use "v5.2" instead of "v5.2 (Stable)").
*   **`play_radio_stream_v2.py` Behavior**: This script pre-fetches KOZT metadata before starting playback to ensure the correct UI is displayed immediately, replacing the default "Radio Paradise" placeholder.

## Pixel Tablet & Smart Display Constraints

*   **Hub Mode / Lock Screen**: To prevent the device from falling back to the default "Media Widget" or Screensaver:
    *   The receiver must play an **active video session**.
    *   **`index.html`**: Must have `touchScreenOptimizedApp = true` and a `cast-media-player` element that is technically "visible" (full-screen, `visibility: visible`) but visually hidden (e.g., `opacity: 0.00001`, `transform: scale(0.0001)`).
    *   **Sender**: In "No-Stream" (`-ns`) mode, use a silent MP3 loop with `metadataType: 1` (MOVIE) and send `QUEUE_UPDATE` with `repeatMode="REPEAT_SINGLE"`.
*   **Authorization**: Launching on a locked Pixel Tablet triggers `USER_PENDING_AUTHORIZATION`. The screen lock must be disabled or the device unlocked to launch.
*   **System Dimming**: The OS applies a dimming overlay on launch. This cannot be dismissed programmatically; the user must tap the screen once.