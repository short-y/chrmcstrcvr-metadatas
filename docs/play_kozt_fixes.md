# play_kozt.py Cleanup Fixes

## Problem
The PyInstaller `--onefile` binary wasn't properly stopping the Chromecast receiver when the process was terminated. This is the same issue that was fixed in `kozt_lite.py`.

## Root Causes
1. **Zeroconf wasn't being closed** - The zeroconf instance created by pychromecast was never properly closed, leaving network connections open
2. **No atexit handler** - Signal handlers alone aren't always reliable in PyInstaller binaries
3. **Separate zeroconf instances** - Each function call created its own zeroconf instance, making cleanup harder

## Changes Made

### 1. Added Global Zeroconf Tracking
- Added `current_zconf` to global state
- All zeroconf instances now stored in this global variable for proper cleanup

### 2. Improved Signal Handler (`graceful_exit`)
- Added `cleanup_in_progress` flag to prevent double-cleanup
- Added explicit steps with status messages:
  - Stop media controller
  - Quit Cast app (with error handling)
  - Stop discovery browser
  - **Close zeroconf** (NEW)
- Added small delays to ensure commands are sent over network

### 3. Added atexit Handler
- Registered `cleanup_atexit()` as backup cleanup mechanism
- Provides additional safety net for PyInstaller binaries
- Only runs if signal handler hasn't already cleaned up

### 4. Unified Zeroconf Management
- `play_radio()` creates zeroconf once and reuses it
- `discover_all_chromecasts()` reuses existing zeroconf if available
- Passed zeroconf to `get_listed_chromecasts()` via `zeroconf_instance` parameter

## Differences from kozt_lite.py
While the fixes are identical, `play_kozt.py` has additional complexity:
- Uses custom receiver (App ID `6509B35C`) instead of Default Media Receiver
- Implements `RadioController` for custom namespace communication
- Includes PING/PONG heartbeat mechanism
- Has metadata pre-fetching logic

All of these features continue to work with the improved cleanup.

## Testing
Rebuild the binary and test:
```bash
pyinstaller play_kozt.spec
./dist/play_kozt "Device Name"
# Press Ctrl+C and verify:
# - "Signal received. Stopping playback..." message appears
# - "Stopping media controller..." messages appear
# - "Closing zeroconf..." appears
# - Cast device returns to home screen/ambient mode
```

## Related Changes
- See `docs/kozt_lite_fixes.md` for the original fix documentation
- Both scripts now have identical cleanup mechanisms
