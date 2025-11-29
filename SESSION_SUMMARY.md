# Session Summary: Pixel Tablet Hub Mode Fix (v5.26)

**Goal:** 
Force the Google Pixel Tablet (in Hub Mode) to display the Custom Receiver UI instead of the default "Media Widget" or Dashboard, and prevent the screensaver/ambient mode from taking over.

**Findings:**
1.  **Hub Mode / Screensaver:** The Pixel Tablet is aggressive about showing its own dashboard/screensaver for "Audio" apps or idle apps.
2.  **"Video" Requirement:** To force the full-screen app experience, the receiver *must* appear to be playing an active video.
3.  **Authorization:** Launching a custom app while the tablet is **locked and docked** triggers `USER_PENDING_AUTHORIZATION`. **Disabling the screen lock** (or setting to "None") resolves this interaction requirement for launch.
4.  **System Dimming:** When the app launches in Hub Mode, the system applies a "Media Scrim" (dimming overlay) over the content. **Simulated touch events do not dismiss this.** The user **must physically tap the screen once** to dismiss the overlay and brighten the UI.

**Solution Implemented:**
*   **Receiver (`index.html` / `receiver.html` v5.26):**
    *   **`touchScreenOptimizedApp = true`**: Configured for tablet interaction.
    *   **Version Reporting:** Sends version number in `PONG` message for verification.
    *   **Visible Player:** The `cast-media-player` element is set to **full-screen** but visually hidden using `transform: scale(0.0001)` and `opacity: 0.00001`. This tricks the OS into maintaining "Video Mode" without blocking the custom UI.
    *   **Hidden Controls:** Internal player UI is hidden via CSS variables and Shadow DOM injection.
    *   **Interaction Simulation:** (v5.26) Attempts to dispatch touch events periodically to wake the screen, though effectiveness is limited by browser security models.
*   **Sender (`play_kozt.py`):**
    *   **Silent Track:** In "No-Stream" (`-ns`) mode, plays a silent MP3 (`audio/mp3`) loop.
    *   **Metadata:** Sends `metadataType: 1` (MOVIE).
    *   **Looping:** Sends `QUEUE_UPDATE` with `repeatMode="REPEAT_SINGLE"` to ensure indefinite playback.
    *   **Launch Logic:** `quit_app()` is commented out.

**Operational Guide:**
1.  **Prerequisite:** Disable Screen Lock on the Pixel Tablet (Settings > Security > Screen lock > None).
2.  **Start:** `python3 play_kozt.py "Your Tablet Name" -ns`
3.  **Action:** The app will launch. **Tap the screen once** to dismiss the initial dimming/overlay.
4.  **Result:** The Custom Receiver stays visible and bright, blocking the screensaver.

**Current Version:** v5.26