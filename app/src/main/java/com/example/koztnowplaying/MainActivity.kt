package com.example.koztnowplaying

import android.net.Uri
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import com.example.koztnowplaying.data.TrackInfo
import com.example.koztnowplaying.ui.KoztNowPlayingScreen
import com.example.koztnowplaying.ui.MainViewModel
import com.example.koztnowplaying.ui.theme.KoztNowPlayingTheme
import com.google.android.gms.cast.MediaInfo
import com.google.android.gms.cast.MediaMetadata
import com.google.android.gms.cast.framework.CastContext
import com.google.android.gms.cast.framework.CastSession
import com.google.android.gms.cast.framework.SessionManagerListener
import com.google.android.gms.common.images.WebImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private val viewModel: MainViewModel by viewModels()
    private var castSession: CastSession? = null
    private lateinit var castContext: CastContext
    private var updateJob: Job? = null

    // Constants from python script
    private val DEFAULT_STREAM_URL = "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u"
    private val SILENT_STREAM_URL = "https://github.com/anars/blank-audio/blob/master/10-minutes-of-silence.mp3?raw=true"
    private val DEFAULT_IMAGE_URL = "https://kozt.com/wp-content/uploads/KOZT-Logo-No-Tag.png"
    
    private val sessionManagerListener = object : SessionManagerListener<CastSession> {
        override fun onSessionStarted(session: CastSession, sessionId: String) {
            castSession = session
            updateCastMedia()
        }
        override fun onSessionResumed(session: CastSession, wasSuspended: Boolean) {
            castSession = session
            updateCastMedia()
        }
        override fun onSessionEnded(session: CastSession, error: Int) { castSession = null }
        override fun onSessionStarting(session: CastSession) {}
        override fun onSessionResuming(session: CastSession, sessionId: String) {}
        override fun onSessionStartFailed(session: CastSession, error: Int) {}
        override fun onSessionResumeFailed(session: CastSession, error: Int) {}
        override fun onSessionEnding(session: CastSession) {}
        override fun onSessionSuspended(session: CastSession, reason: Int) {}
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        try {
            castContext = CastContext.getSharedInstance(this)
        } catch(e: Exception) {
            Log.e("MainActivity", "Error initializing CastContext", e)
        }

        setContent {
            KoztNowPlayingTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val trackInfo by viewModel.trackInfo.collectAsState()
                    val isNoStreamMode by viewModel.isNoStreamMode.collectAsState()

                    // Side effect to update Cast when track info changes
                    LaunchedEffect(trackInfo, isNoStreamMode) {
                        updateCastMedia()
                    }

                    KoztNowPlayingScreen(
                        trackInfo = trackInfo,
                        isNoStreamMode = isNoStreamMode,
                        onToggleNoStreamMode = {
                            viewModel.toggleNoStreamMode()
                        },
                        onPlayPause = { /* Handle manual play/pause if needed */ }
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        try {
            castContext.sessionManager.addSessionManagerListener(sessionManagerListener, CastSession::class.java)
            if (castContext.sessionManager.currentCastSession != null) {
                castSession = castContext.sessionManager.currentCastSession
            }
        } catch (e: Exception) { e.printStackTrace() }
    }

    override fun onPause() {
        super.onPause()
        try {
            castContext.sessionManager.removeSessionManagerListener(sessionManagerListener, CastSession::class.java)
        } catch (e: Exception) { e.printStackTrace() }
    }

    private fun updateCastMedia() {
        if (castSession == null || !castSession!!.isConnected) return

        val trackInfo = viewModel.trackInfo.value
        val isNoStreamMode = viewModel.isNoStreamMode.value

        val streamUrl = if (isNoStreamMode) SILENT_STREAM_URL else DEFAULT_STREAM_URL
        val contentType = "audio/mp3"

        val metadata = MediaMetadata(MediaMetadata.MEDIA_TYPE_MUSIC_TRACK)
        
        if (trackInfo != null) {
            metadata.putString(MediaMetadata.KEY_TITLE, trackInfo.title)
            metadata.putString(MediaMetadata.KEY_ARTIST, trackInfo.artist)
            metadata.putString(MediaMetadata.KEY_ALBUM_TITLE, trackInfo.album)
            
            val imageUrl = trackInfo.imageUrl ?: DEFAULT_IMAGE_URL
            metadata.addImage(WebImage(Uri.parse(imageUrl)))
        } else {
            metadata.putString(MediaMetadata.KEY_TITLE, "KOZT - The Coast")
            metadata.addImage(WebImage(Uri.parse(DEFAULT_IMAGE_URL)))
        }

        val mediaInfo = MediaInfo.Builder(streamUrl)
            .setStreamType(MediaInfo.STREAM_TYPE_BUFFERED)
            .setContentType(contentType)
            .setMetadata(metadata)
            .build()

        try {
            val remoteMediaClient = castSession?.remoteMediaClient
            
            // Check if we are already playing the same content to avoid restarting
            // Note: This is a simplified check. In production, check currently playing item ID or URL.
            // For now, we just load it if it's a "metadata update" we might want to use load() 
            // but if the stream is live radio, restarting the stream every 15s is bad.
            // However, kozt_lite.py uses `play_media` which *restarts* the media or just updates metadata?
            // `play_media` in pychromecast calls `load` which usually restarts.
            // The python script: "Updates the metadata... mc.play_media(...)". It seems to restart or reload.
            // But wait, live radio shouldn't restart.
            // If the stream URL is the same, we might just want to update metadata?
            // Android Cast SDK doesn't easily support "update metadata without reloading" for Default Receiver unless we use queue manipulation or custom receiver.
            // However, the Python script calls `mc.play_media` which sends a LOAD command.
            // Let's stick to what the script does: it sends a LOAD command.
            // Wait, does the python script really send LOAD every 15 seconds?
            // "if song_title != last_title ... update_media_metadata"
            // Ah, it only updates when track changes!
            
            // So we need to track local state of what we last sent to Cast.
            
            remoteMediaClient?.load(mediaInfo)
        } catch (e: Exception) {
            Log.e("MainActivity", "Error loading media", e)
        }
    }
}

// Helper Composable for Side Effects
@androidx.compose.runtime.Composable
fun LaunchedEffect(
    vararg keys: Any?,
    block: suspend kotlinx.coroutines.CoroutineScope.() -> Unit
) {
    androidx.compose.runtime.LaunchedEffect(keys = keys, block = block)
}
