# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chromecast internet radio application specifically designed for KOZT - The Coast (Mendocino County Public Broadcasting), with support for generic internet radio streams. The project has two implementations:

1. **Full version** (`play_kozt.py`) - Uses a custom HTML5 receiver with advanced UI overlay
2. **Lite version** (`kozt_lite.py`) - Uses the standard Default Media Receiver (simpler, no custom app registration needed)

**Custom Receiver URL:** https://short-y.github.io/chrmcstrcvr-metadatas/index.html
**Custom Receiver App ID:** `6509B35C`

## Environment Setup

### Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Dependencies:** `pychromecast`, `zeroconf`, `requests`

### Development Registration (for play_kozt.py only)
The Chromecast device serial number must be registered in the [Google Cast SDK Developer Console](https://cast.google.com/publish) when using the custom receiver. Devices may need to be rebooted after registration.

## Running the Application

### Full Version: play_kozt.py (Custom Receiver)

**Basic playback:**
```bash
python3 play_kozt.py "Living Room TV"
```

**No-stream mode** (for smart displays - launches UI without audio):
```bash
python3 play_kozt.py "Pixel Tablet" -ns
```

**Logging levels:**
- Default: `WARNING` level (minimal output)
- `--debug`: `INFO` level (heartbeats, metadata refresh intervals)
- `--verbose`: `DEBUG` level (full internal Cast protocol logs)

**Generic station:**
```bash
python3 play_kozt.py "Device Name" --url "http://stream.example.com/radio" --title "Station Name" --no-kozt
```

### Lite Version: kozt_lite.py (Default Media Receiver)

**Basic playback:**
```bash
python3 kozt_lite.py "Living Room TV"
```

**No-stream mode** (metadata only with silent audio):
```bash
python3 kozt_lite.py "Pixel Tablet" -ns
```

This version is simpler but relies on the Default Media Receiver's standard UI. No custom app registration required.

### Building Standalone Binaries

PyInstaller configurations provided:
```bash
pyinstaller play_kozt.spec        # Full version
pyinstaller kozt_lite.spec        # Lite version
```
Output: `dist/play_kozt` or `dist/kozt_lite` executables

## Architecture

### Sender Scripts (Python)

**play_kozt.py** (full version with custom receiver):
- **Uses custom receiver by default** (App ID `6509B35C`)
- Pre-fetches metadata before launching to improve initial display
- KOZT-specific: Polls Amperwave JSON API (`api-nowplaying.amperwave.net`) with randomized 10-25s intervals
- Generic streams: Reads interleaved Icecast metadata from stream headers (`Icy-MetaInt`)
- Fallback album art: iTunes Search API
- Custom namespace: `urn:x-cast:com.example.radio`
- Implements PING/PONG heartbeat with exponential backoff and reconnection logic
- Handles `USER_PENDING_AUTHORIZATION` errors for locked devices
- Uses `RadioController` for custom messaging to receiver

**kozt_lite.py** (lite version with Default Media Receiver):
- **Uses standard Default Media Receiver** (no custom app needed)
- Simpler implementation without custom receiver complexity
- Updates metadata using standard CAF `play_media()` calls with metadata parameter
- KOZT-specific: Polls Amperwave JSON API every 15 seconds
- Fallback album art: iTunes Search API
- Signal handling for graceful cleanup (SIGINT/SIGTERM)
- No PING/PONG or custom namespace needed

**play_radio_stream_v2.py** (generic reference implementation):
- Uses standard Default Media Receiver by default
- Can optionally use custom receiver with `--app_id` parameter
- Similar architecture to play_kozt.py but without KOZT-specific defaults
- Optional KOZT mode via `--kozt` flag

**Helper utilities:**
- `icecast_metadata_reader.py`: Standalone tool to inspect Icecast stream headers and metadata
- `display_dashboard.py`: Silent stream player for keeping displays active
- `discovery_example*.py`: pychromecast discovery reference examples

### Receiver (HTML/JavaScript)

**index.html** (production receiver for play_kozt.py):
- Uses Cast Application Framework (CAF) v3
- Custom namespace: `urn:x-cast:com.example.radio`
- Responds to sender messages: track metadata updates, PING/PONG keepalives
- `touchScreenOptimizedApp = true` for tablet support

**Pixel Tablet Hub Mode workaround:**
- Must play an active "video" session (uses `metadataType: 1` MOVIE) to prevent screensaver
- Hidden `cast-media-player` element (full-screen but `opacity: 0.00001`, `transform: scale(0.0001)`)
- In no-stream mode, plays silent MP3 loop with `REPEAT_SINGLE`

**Version synchronization:**
- `receiver.html` must be an exact copy of `index.html`
- Version numbers incremented in both files when changes are made
- Version strings exclude labels like "Stable" or "Robust" (e.g., "v5.26")

### Communication Flow

#### Full Version (play_kozt.py with custom receiver):
1. Sender resolves playlist URLs (`.m3u`/`.pls`) to direct stream URLs
2. Sender launches custom receiver via App ID `6509B35C`
3. Sender plays media via CAF MediaController with minimal metadata (to avoid default UI clutter)
4. Sender immediately pushes rich metadata via `RadioController` custom messages
5. For KOZT: Sender polls JSON API and pushes updates to receiver
6. For generic: Sender reads stream metadata and pushes updates
7. Receiver updates custom UI overlay (z-index 20000+) that covers default CAF UI

#### Lite Version (kozt_lite.py with Default Media Receiver):
1. Sender resolves playlist URLs to direct stream URLs
2. Sender plays media via Default Media Receiver (auto-launched by `play_media()`)
3. Sender uses standard metadata parameter in `play_media()` calls
4. For KOZT: Sender polls JSON API every 15 seconds
5. On track change, sender calls `play_media()` again with updated metadata
6. Default Media Receiver displays standard UI with updated information

## Pixel Tablet Constraints

**Hub Mode / Lock Screen Behavior:**
- Device must have screen lock disabled (Settings > Security > Screen lock > None) to avoid `USER_PENDING_AUTHORIZATION` on launch
- Must play active video session to prevent fallback to Media Widget/Dashboard (applies to custom receiver version)
- System applies dimming overlay ("Media Scrim") on launch that cannot be dismissed programmatically
- User must physically tap screen once to dismiss overlay and brighten UI

## Key Implementation Patterns

### Metadata Pre-fetching (play_kozt.py)
Fetches metadata before starting playback to ensure the receiver displays correct information immediately on launch rather than showing defaults.

### Metadata Updates via play_media() (kozt_lite.py)
Simpler approach: on track change, calls `play_media()` again with the same stream URL but updated metadata. The Default Media Receiver handles the UI update.

### Heartbeat Protocol (play_kozt.py only)
Custom PING/PONG messages via `RadioController` verify the receiver connection independently of CAF status. The sender tracks consecutive failures (3-strike threshold) before reconnecting.

### Stream Type Trick (play_kozt.py)
Stream `content_type` is set to `"video/mp4"` instead of `"audio/mp3"` to force video mode behavior, which prevents persistent audio control UI on some devices.

### No-Stream Mode
When `-ns` flag is used, sender plays a silent MP3 loop to keep the receiver active while updating metadata, allowing users to listen via separate hardware while viewing metadata on the display.

### Signal Handling (kozt_lite.py)
Implements graceful cleanup for SIGINT/SIGTERM to properly stop playback and quit the app when the process is killed.

## File Roles

- `play_kozt.py`: Production KOZT sender with custom receiver
- `play_kozt.spec`: PyInstaller build configuration for full version
- `kozt_lite.py`: Simplified KOZT sender using Default Media Receiver
- `kozt_lite.spec`: PyInstaller build configuration for lite version
- `play_radio_stream_v2.py`: Generic reference implementation
- `index.html`: Production custom receiver (must match receiver.html)
- `receiver.html`: Backup copy of production custom receiver
- `00-HOWTO-run.txt`: User-facing operational guide
- `SESSION_SUMMARY.md`: Development session notes on Pixel Tablet fixes
- `GEMINI.md`: Project-specific conventions and constraints

## Testing Workflow

1. Test changes to custom receiver by editing `index.html` (GitHub Pages auto-deploys)
2. Test full version sender by running `play_kozt.py` with `--verbose` flag to see full protocol logs
3. Test lite version sender by running `kozt_lite.py`
4. For Pixel Tablet testing: disable screen lock, use `-ns` mode, tap screen after launch
5. Verify version synchronization between `index.html` and `receiver.html`
