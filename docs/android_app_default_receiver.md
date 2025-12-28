# Android App with Default Media Receiver - Testing Analysis

**Date**: 2025-12-28
**App Version**: 1.6 (code 7)
**Receiver**: Default Media Receiver (Google's standard receiver)
**Application ID**: `CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID`

## Overview

This document analyzes the Android app's functionality when using the Google Default Media Receiver. Unlike the custom receiver (App ID: 6509B35C), the Default Media Receiver is a standard Google-provided receiver that requires no registration and uses standard Cast protocols.

---

## Android App Configuration

### CastOptionsProvider (app/src/main/java/com/tonystakeontech/castkozt/CastOptionsProvider.kt)

```kotlin
class CastOptionsProvider : OptionsProvider {
    override fun getCastOptions(context: Context): CastOptions {
        return CastOptions.Builder()
            .setReceiverApplicationId(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID)
            .build()
    }
}
```

**Key Points**:
- ✅ Uses Default Media Receiver (no custom app ID needed)
- ✅ No device registration required
- ✅ Works on any Chromecast device immediately
- ✅ Standard Google UI and controls

---

## Metadata Transmission

### updateCastMedia() Implementation (MainActivity.kt:302-349)

The app sends metadata using standard Cast protocols:

```kotlin
val metadata = MediaMetadata(MediaMetadata.MEDIA_TYPE_MUSIC_TRACK)

if (trackInfo != null) {
    metadata.putString(MediaMetadata.KEY_TITLE, trackInfo.title)
    metadata.putString(MediaMetadata.KEY_ARTIST, trackInfo.artist)
    metadata.putString(MediaMetadata.KEY_ALBUM_TITLE, trackInfo.album)

    val imageUrl = trackInfo.imageUrl ?: DEFAULT_IMAGE_URL
    metadata.addImage(WebImage(Uri.parse(imageUrl)))
}

val mediaInfo = MediaInfo.Builder(streamUrl)
    .setStreamType(MediaInfo.STREAM_TYPE_BUFFERED)
    .setContentType(contentType)  // "audio/aac" or "audio/mp3"
    .setMetadata(metadata)
    .build()

remoteMediaClient?.load(mediaInfo)
```

### Metadata Fields Sent

| Field | Type | Example Value |
|-------|------|---------------|
| Media Type | `MEDIA_TYPE_MUSIC_TRACK` | Music track (not movie/photo) |
| Title | `KEY_TITLE` | "Coastal Sunset" |
| Artist | `KEY_ARTIST` | "The Ocean Waves" |
| Album | `KEY_ALBUM_TITLE` | "Sounds of Nature" |
| Image | `WebImage` | Album artwork URL |
| Stream URL | Audio URL | AAC stream or silent MP3 |
| Content Type | MIME type | "audio/aac" or "audio/mp3" |
| Stream Type | `STREAM_TYPE_BUFFERED` | Buffered (not live) |

---

## Default Media Receiver Behavior

### Expected Display

The Default Media Receiver will show:

1. **Album artwork** - Large centered image
2. **Song title** - Below the artwork
3. **Artist name** - Below the title
4. **Album name** - Below the artist
5. **Playback controls** - Play/pause, volume
6. **Progress bar** - For buffered streams (though radio is continuous)

### UI Characteristics

- **Google's standard UI**: Dark background, white text
- **No customization**: Cannot override colors, fonts, or layout
- **Automatic updates**: When `load()` is called again with new metadata
- **Persistent controls**: Standard Cast controls visible
- **Screen saver**: May activate after period of inactivity (unlike custom receiver)

---

## Data Flow

### 1. App Startup Sequence

```
MainActivity.onCreate()
  ↓
ViewModel.init()
  ↓
resolveStream() - Resolves M3U playlist to direct stream URL
  ↓
startPolling() - Begins fetching metadata every 15 seconds
  ↓
(Waits for user to connect to Chromecast)
```

### 2. Cast Session Started

```
SessionManagerListener.onSessionStarted()
  ↓
castSession = session
  ↓
updateCastMedia() - Sends initial metadata
  ↓
remoteMediaClient.load(mediaInfo)
  ↓
Default Media Receiver displays content
```

### 3. Metadata Update Cycle

```
Every 15 seconds:
  ViewModel.startPolling()
    ↓
  KoztRepository.fetchNowPlaying()
    ↓
  Amperwave API: api-nowplaying.amperwave.net
    ↓
  trackInfo.value = new track data
    ↓
  LaunchedEffect triggers (TrackInfo changed)
    ↓
  updateCastMedia() called
    ↓
  remoteMediaClient.load(newMediaInfo)
    ↓
  Default Media Receiver updates display
```

### 4. App Backgrounded (HOME key)

```
MainActivity.onPause()
  ↓
MainActivity.onStop()
  ↓
MulticastLock released
Session listeners removed
  ↓
ViewModel continues polling (every 15s)
Cast session stays active
Receiver continues playing
  ↓
User returns to app
  ↓
MainActivity.onStart()
  ↓
MulticastLock re-acquired
Session listeners re-registered
Updates resume
```

### 5. App Exited (BACK key)

```
MainActivity.onPause()
  ↓
MainActivity.onStop()
  ↓
MainActivity.onDestroy()
  ↓
castSession?.remoteMediaClient?.stop()
castContext.sessionManager.endCurrentSession(true)
  ↓
ViewModel.onCleared()
  ↓
Polling job cancelled
All resources released
  ↓
Receiver stops playback
```

---

## Differences: Default vs Custom Receiver

| Feature | Default Media Receiver | Custom Receiver (v5.26) |
|---------|----------------------|------------------------|
| **App ID** | Built-in | 6509B35C |
| **Registration** | None required | Device serial must be registered |
| **UI Customization** | None | Full control (HTML/CSS/JS) |
| **Metadata Updates** | Via `load()` | Via custom messages + `load()` |
| **PING/PONG** | Not needed | Required for connection monitoring |
| **Screen Saver** | Standard behavior | Can be prevented (Pixel Tablet workaround) |
| **Station Name** | Not displayed | Displayed at top |
| **Time Display** | Not shown | Shows converted local time |
| **Version Tag** | Not shown | Shows receiver version |
| **Background Blur** | None | Album art blurred in background |
| **Message Bus** | Standard only | Custom namespace available |
| **Update Method** | Full reload | Can update individual fields |

---

## Android App Features

### Metadata Fetching

**Source**: Amperwave JSON API
```
https://api-nowplaying.amperwave.net/index.php
  ?station=kozt
  &callsign=KOZT-FM
```

**Polling Interval**: 15 seconds (MainViewModel.kt:87)

**Data Extracted**:
- Track title
- Artist name
- Album name
- Album artwork URL (from API or iTunes fallback)

### Stream Resolution

**M3U Playlist**:
```
https://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u
```

**Resolved to**: Direct AAC stream URL

**Fallback**: Uses M3U URL if resolution fails

### No-Stream Mode

**Purpose**: Display metadata without audio (for smart displays when user has separate radio)

**Implementation**:
- Stream URL: Silent 10-minute MP3 loop
- Content Type: `audio/mp3`
- Metadata: Same as normal mode
- User toggles via UI switch

**Use Case**: Pixel Tablet showing "now playing" while audio plays on physical radio

### Lifecycle Management (v1.6 improvements)

**Resource Acquisition** (onStart):
- MulticastLock for Cast discovery
- Session manager listeners
- MediaRouter callbacks

**Resource Release** (onStop):
- MulticastLock released
- Listeners removed
- ViewModel continues running (polling persists)

**Full Cleanup** (onDestroy):
- Stop Cast session
- End current session
- Cancel all jobs
- Clear all references

---

## Testing Scenarios

### Scenario 1: Normal Playback

**Steps**:
1. Open Android app
2. Tap Cast button
3. Select Chromecast device
4. Wait for connection

**Expected Behavior**:
- ✅ App resolves stream URL
- ✅ App fetches current track metadata
- ✅ Default Media Receiver launches
- ✅ Stream begins playing
- ✅ Metadata displays (title, artist, album, artwork)
- ✅ App updates metadata every 15 seconds
- ✅ Receiver UI updates when track changes

### Scenario 2: No-Stream Mode

**Steps**:
1. Connect to Cast device
2. Toggle "No-Stream Mode" in app
3. Observe behavior

**Expected Behavior**:
- ✅ Silent MP3 loop plays instead of KOZT stream
- ✅ Metadata still updates every 15 seconds
- ✅ Display shows current track info
- ✅ User can listen on separate hardware radio

**Use Case**: Pixel Tablet as "now playing" display

### Scenario 3: App Backgrounded

**Steps**:
1. Start casting
2. Press HOME button
3. Wait 2-3 minutes
4. Return to app

**Expected Behavior**:
- ✅ Casting continues while app backgrounded
- ✅ Metadata updates continue (polling runs in background)
- ✅ MulticastLock released (saves battery)
- ✅ When returning, MulticastLock re-acquired
- ✅ No interruption to playback

### Scenario 4: App Exited

**Steps**:
1. Start casting
2. Press BACK button to exit app
3. Observe Cast device

**Expected Behavior**:
- ✅ Cast session stops
- ✅ Playback ends
- ✅ Receiver exits to idle screen
- ✅ All resources released (no memory leaks)
- ✅ MulticastLock released

### Scenario 5: Track Changes

**Steps**:
1. Start casting during middle of song
2. Wait for next song to start (on radio)
3. Wait up to 15 seconds for app to poll

**Expected Behavior**:
- ✅ App polls API every 15 seconds
- ✅ New metadata detected
- ✅ App calls `load()` with updated metadata
- ✅ Receiver displays new track info
- ✅ New album art loads
- ✅ Stream continues without interruption

---

## Limitations vs Custom Receiver

### What Default Receiver Cannot Do

1. **No station name display** - Only shows track metadata
2. **No time display** - Cannot show broadcast time
3. **No version info** - Cannot display app/receiver version
4. **No PING/PONG** - Cannot monitor connection health actively
5. **Screen saver issue** - May activate on idle (Pixel Tablet problem)
6. **UI locked to Google's design** - No customization possible
7. **No custom messages** - Cannot send app-specific data

### What Works Fine with Default Receiver

1. ✅ **Standard metadata** - Title, artist, album, artwork
2. ✅ **Playback control** - Play/pause/volume
3. ✅ **Metadata updates** - Via repeated `load()` calls
4. ✅ **No registration** - Works on any device immediately
5. ✅ **Reliable** - Google-maintained receiver
6. ✅ **Standard UI** - Familiar to users

---

## Code Quality Assessment

### Strengths (v1.6)

1. ✅ **Proper lifecycle management** - Resources acquired/released correctly
2. ✅ **Clean separation** - ViewModel handles data, Activity handles UI
3. ✅ **Logging** - Comprehensive logs for debugging
4. ✅ **Error handling** - Try/catch blocks on critical operations
5. ✅ **Background polling** - Metadata updates automatically
6. ✅ **Stream resolution** - Handles M3U playlists
7. ✅ **No-stream mode** - Flexible usage scenarios
8. ✅ **Graceful cleanup** - Proper onDestroy implementation

### Architecture

```
KoztApp (Application)
  ↓
MainActivity (AppCompatActivity)
  ├─ CastContext / SessionManager
  ├─ MediaRouter (for device discovery)
  ├─ MulticastLock (for mDNS discovery)
  └─ MainViewModel
      ├─ KoztRepository
      │   ├─ KoztApiService (Amperwave)
      │   └─ ITunesApiService (fallback artwork)
      └─ Coroutines for polling
```

### Dependencies

- **Cast SDK**: `com.google.android.gms:play-services-cast-framework`
- **MediaRouter**: `androidx.mediarouter:mediarouter`
- **Retrofit**: For API calls
- **Gson**: JSON parsing
- **Coil**: Image loading (for UI preview)
- **Compose**: UI framework

---

## Recommendations

### For Default Media Receiver Usage

1. **Keep using Default Receiver if**:
   - No custom UI needed
   - Standard metadata display is sufficient
   - Want zero setup (no device registration)
   - Google's UI is acceptable

2. **Switch to Custom Receiver if**:
   - Need station name display
   - Need time display
   - Need PING/PONG monitoring
   - Want custom branding/UI
   - Need Pixel Tablet screen saver workaround

### Testing Checklist

Before Play Store release, test:

- [ ] Cast discovery on multiple Chromecast models
- [ ] Metadata updates during playback
- [ ] App backgrounding (HOME key)
- [ ] App exit (BACK key)
- [ ] No-stream mode toggle
- [ ] Stream resolution from M3U
- [ ] Album art loading
- [ ] Network interruptions
- [ ] Multiple track changes
- [ ] Permission grants (first launch)

---

## Conclusion

The Android app (v1.6) is **well-designed** for use with the Default Media Receiver:

✅ **Proper lifecycle management** - v1.6 fixes ensure clean exit and background behavior
✅ **Standard Cast protocols** - Uses official APIs correctly
✅ **Automatic metadata updates** - Polling ensures current track info
✅ **Flexible modes** - Normal and no-stream modes supported
✅ **Production-ready** - Clean architecture, error handling, logging

The Default Media Receiver provides a **simple, reliable solution** that works immediately without device registration. For users who need advanced features (station name, time display, custom UI), the custom receiver (App ID: 6509B35C) is available as an alternative.
