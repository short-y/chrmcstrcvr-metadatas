package com.example.castkozt

import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.mediarouter.media.MediaControlIntent
import androidx.mediarouter.media.MediaRouteSelector
import androidx.mediarouter.media.MediaRouter
import com.example.castkozt.data.TrackInfo
import com.example.castkozt.ui.KoztNowPlayingScreen
import com.example.castkozt.ui.MainViewModel
import com.example.castkozt.ui.theme.KoztNowPlayingTheme
import com.google.android.gms.cast.CastMediaControlIntent
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
    private var mediaRouter: MediaRouter? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var updateJob: Job? = null

    // Constants from python script
    private val DEFAULT_STREAM_URL = "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u"
    private val SILENT_STREAM_URL = "https://github.com/anars/blank-audio/blob/master/10-minutes-of-silence.mp3?raw=true"
    private val DEFAULT_IMAGE_URL = "https://kozt.com/wp-content/uploads/KOZT-Logo-No-Tag.png"
    
    private val requestPermissionLauncher: ActivityResultLauncher<Array<String>> =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { permissions ->
            permissions.entries.forEach {
                viewModel.appendLog("Permission '${it.key}' granted: ${it.value}")
            }
        }

    private val mediaRouterCallback = object : MediaRouter.Callback() {
        override fun onRouteAdded(router: MediaRouter, route: MediaRouter.RouteInfo) {
            viewModel.appendLog("Route added: ${route.name} (${route.id}) Desc: ${route.description}")
        }
        override fun onRouteRemoved(router: MediaRouter, route: MediaRouter.RouteInfo) {
            viewModel.appendLog("Route removed: ${route.name}")
        }
        override fun onRouteSelected(router: MediaRouter, route: MediaRouter.RouteInfo) {
            viewModel.appendLog("Route selected: ${route.name}")
        }
        override fun onRouteUnselected(router: MediaRouter, route: MediaRouter.RouteInfo) {
            viewModel.appendLog("Route unselected: ${route.name}")
        }
    }

    // ...

                val selector = MediaRouteSelector.Builder()
                    .addControlCategory(CastMediaControlIntent.categoryForCast(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID))
                    .addControlCategory("com.google.android.gms.cast.CATEGORY_CAST") // Generic Cast discovery
                    .addControlCategory(MediaControlIntent.CATEGORY_LIVE_AUDIO)
                    .addControlCategory(MediaControlIntent.CATEGORY_REMOTE_PLAYBACK)
                    .build()
                
                viewModel.appendLog("Registering MediaRouter callback with BROADENED selector...")
                mediaRouter?.addCallback(selector, mediaRouterCallback, MediaRouter.CALLBACK_FLAG_REQUEST_DISCOVERY)
            }
        } catch (e: Exception) {
            viewModel.appendLog("Error in onResume adding listeners: ${e.message}")
            e.printStackTrace()
        }
    }

    override fun onPause() {
        super.onPause()
        viewModel.appendLog("MainActivity onPause.")
        
        try {
            multicastLock?.release()
            viewModel.appendLog("MulticastLock released.")
        } catch (e: Exception) {
            // Ignore release errors
        }

        try {
            castContext.sessionManager.removeSessionManagerListener(sessionManagerListener, CastSession::class.java)
            mediaRouter?.removeCallback(mediaRouterCallback)
        } catch (e: Exception) {
            viewModel.appendLog("Error in onPause removing listeners: ${e.message}")
            e.printStackTrace()
        }
    }

    @Suppress("DEPRECATION")
    private fun updateCastMedia() {
        if (castSession == null || !castSession!!.isConnected) {
            viewModel.appendLog("Cannot update Cast media: Not connected to CastSession.")
            return
        }

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
            viewModel.appendLog("Metadata prepared: ${trackInfo.title} by ${trackInfo.artist}")
        } else {
            metadata.putString(MediaMetadata.KEY_TITLE, "KOZT - The Coast")
            metadata.addImage(WebImage(Uri.parse(DEFAULT_IMAGE_URL)))
            viewModel.appendLog("Metadata prepared: Default KOZT.")
        }

        val mediaInfo = MediaInfo.Builder(streamUrl)
            .setStreamType(MediaInfo.STREAM_TYPE_BUFFERED)
            .setContentType(contentType)
            .setMetadata(metadata)
            .build()

        try {
            val remoteMediaClient = castSession?.remoteMediaClient
            viewModel.appendLog("Loading media to Cast device: $streamUrl (NoStreamMode: $isNoStreamMode)")
            remoteMediaClient?.load(mediaInfo)
        } catch (e: Exception) {
            viewModel.appendLog("Error loading media to Cast device: ${e.message}")
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