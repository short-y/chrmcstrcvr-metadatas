# play_kozt.py Cleanup Fixes

## Problems Fixed

### Issue 1: Incomplete Cleanup (Original)
The PyInstaller `--onefile` binary wasn't properly stopping the Chromecast receiver when the process was terminated. This is the same issue that was fixed in `kozt_lite.py`.

### Issue 2: Reentrant Call Error (December 2025)
When pressing Ctrl+C, the program displayed:
```
Error: reentrant call inside <_io.BufferedWriter name='<stdout>'>
```
And the script would restart instead of stopping.

## Root Causes

### Original Issues
1. **Zeroconf wasn't being closed** - The zeroconf instance created by pychromecast was never properly closed, leaving network connections open
2. **No atexit handler** - Signal handlers alone aren't always reliable in PyInstaller binaries
3. **Separate zeroconf instances** - Each function call created its own zeroconf instance, making cleanup harder

### Reentrant Call Issues
4. **Non-signal-safe print()** - Using `print()` inside signal handlers causes reentrant errors when interrupting another print operation
5. **Reconnection loop not checking cleanup flag** - The `while True` loop would catch exceptions and restart even during cleanup

## Changes Made

### 1. Added Global Zeroconf Tracking (Original Fix)
- Added `current_zconf` to global state
- All zeroconf instances now stored in this global variable for proper cleanup

### 2. Improved Signal Handler (`graceful_exit`) (Original + Updated)
- Added `cleanup_in_progress` flag to prevent double-cleanup
- **NEW: Signal-safe output via `safe_write()`** - Replaced all `print()` calls with `os.write()` to prevent reentrant errors
- **NEW: Use `os._exit()` instead of `sys.exit()`** - Ensures immediate termination without triggering Python cleanup that could cause issues
- Added explicit steps with status messages:
  - Stop media controller
  - Quit Cast app (with error handling)
  - Stop discovery browser
  - Close zeroconf
- Added small delays to ensure commands are sent over network

### 3. Added atexit Handler (Original + Updated)
- Registered `cleanup_atexit()` as backup cleanup mechanism
- Provides additional safety net for PyInstaller binaries
- **NEW: Simplified to avoid recursive calls** - Now performs cleanup directly instead of calling `graceful_exit()`
- Only runs if signal handler hasn't already cleaned up

### 4. Unified Zeroconf Management (Original Fix)
- `play_radio()` creates zeroconf once and reuses it
- `discover_all_chromecasts()` reuses existing zeroconf if available
- Passed zeroconf to `get_listed_chromecasts()` via `zeroconf_instance` parameter

### 5. Fixed Reconnection Loop (New Fix)
- **NEW: Check `cleanup_in_progress` in exception handler** - Prevents the script from attempting to reconnect when Ctrl+C is pressed
- The `while True` loop now breaks immediately during cleanup instead of restarting

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
# - NO "reentrant call" error appears
# - "Signal received. Stopping playback..." message appears
# - "Stopping media controller..." messages appear
# - "Closing zeroconf..." appears
# - "Exiting." message appears
# - Script exits immediately without restarting
# - Cast device returns to home screen/ambient mode
```

## Expected Ctrl+C Output
```
^C
Signal received. Stopping playback...
Stopping media controller...
Quitting Cast app...
Stopping discovery...
Closing zeroconf...
Exiting.
```

## Related Changes
- See `docs/kozt_lite_fixes.md` for the original fix documentation
- Both scripts now have identical cleanup mechanisms
