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

    private val sessionManagerListener = @Suppress("OVERRIDE_DEPRECATION") object : SessionManagerListener<CastSession> {
        @Suppress("OVERRIDE_DEPRECATION")
        override fun onSessionStarted(session: CastSession, sessionId: String) {
            castSession = session
            viewModel.appendLog("CastSession started: ${session.castDevice?.friendlyName}")
            updateCastMedia()
        }
        @Suppress("OVERRIDE_DEPRECATION")
        override fun onSessionResumed(session: CastSession, wasSuspended: Boolean) {
            castSession = session
            viewModel.appendLog("CastSession resumed: ${session.castDevice?.friendlyName} (wasSuspended: $wasSuspended)")
            updateCastMedia()
        }
        override fun onSessionEnded(session: CastSession, error: Int) {
            castSession = null
            viewModel.appendLog("CastSession ended (error: $error)")
        }
        override fun onSessionStarting(session: CastSession) { viewModel.appendLog("CastSession starting...") }
        override fun onSessionResuming(session: CastSession, sessionId: String) { viewModel.appendLog("CastSession resuming...") }
        override fun onSessionStartFailed(session: CastSession, error: Int) { viewModel.appendLog("CastSession start failed (error: $error)") }
        override fun onSessionResumeFailed(session: CastSession, error: Int) { viewModel.appendLog("CastSession resume failed (error: $error)") }
        override fun onSessionEnding(session: CastSession) { viewModel.appendLog("CastSession ending...") }
        override fun onSessionSuspended(session: CastSession, reason: Int) { viewModel.appendLog("CastSession suspended (reason: $reason)") }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel.appendLog("MainActivity onCreate.")
        
        val permissionsToRequest = mutableListOf<String>()

        // Request permissions for Android 12+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) { // Android 12
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) { // Android 13
                permissionsToRequest.add(android.Manifest.permission.NEARBY_WIFI_DEVICES)
            }
            permissionsToRequest.add(android.Manifest.permission.BLUETOOTH_SCAN)
            permissionsToRequest.add(android.Manifest.permission.BLUETOOTH_CONNECT)
        }
        // Always request Location for older Android versions or robust discovery
        permissionsToRequest.add(android.Manifest.permission.ACCESS_FINE_LOCATION)
        permissionsToRequest.add(android.Manifest.permission.ACCESS_COARSE_LOCATION)

        if (permissionsToRequest.isNotEmpty()) {
            requestPermissionLauncher.launch(permissionsToRequest.toTypedArray())
        }

        try {
            viewModel.appendLog("Initializing CastContext...")
            castContext = CastContext.getSharedInstance(this)
            viewModel.appendLog("CastContext initialized.")
            
            // Initialize MediaRouter
            mediaRouter = MediaRouter.getInstance(this)
            
        } catch(e: Exception) {
            viewModel.appendLog("Error initializing Cast/MediaRouter: ${e.message}")
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
                    val logs by viewModel.logs.collectAsState()

                    // Side effect to update Cast when track info changes
                    LaunchedEffect(trackInfo, isNoStreamMode) {
                        viewModel.appendLog("TrackInfo or NoStreamMode changed. Updating Cast media.")
                        updateCastMedia()
                    }

                    KoztNowPlayingScreen(
                        trackInfo = trackInfo,
                        isNoStreamMode = isNoStreamMode,
                        onToggleNoStreamMode = {
                            viewModel.appendLog("Toggling No-Stream Mode.")
                            viewModel.toggleNoStreamMode()
                        },
                        logs = logs // Pass logs to the screen
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        viewModel.appendLog("MainActivity onResume.")

        // Acquire Multicast Lock
        try {
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("multicastLock")
            multicastLock?.setReferenceCounted(true)
            multicastLock?.acquire()
            viewModel.appendLog("MulticastLock acquired. IsHeld: ${multicastLock?.isHeld}")
        } catch (e: Exception) {
            viewModel.appendLog("Error acquiring MulticastLock: ${e.message}")
        }

        // 1. Explicit Permission Check
        val locationPermission = ContextCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_FINE_LOCATION)
        val bluetoothScanPermission = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ContextCompat.checkSelfPermission(this, android.Manifest.permission.BLUETOOTH_SCAN)
        } else {
            PackageManager.PERMISSION_GRANTED
        }
        
        viewModel.appendLog("Perm Check: Location=${locationPermission == PackageManager.PERMISSION_GRANTED}, BT_Scan=${bluetoothScanPermission == PackageManager.PERMISSION_GRANTED}")

        try {
            castContext.sessionManager.addSessionManagerListener(sessionManagerListener, CastSession::class.java)
            if (castContext.sessionManager.currentCastSession != null) {
                castSession = castContext.sessionManager.currentCastSession
                viewModel.appendLog("Existing CastSession found: ${castSession?.castDevice?.friendlyName}")
            }
            
            // 2. Register MediaRouter callback with BROADENED selector
            if (mediaRouter != null) {
                // Check existing routes first
                val existingRoutes = mediaRouter?.routes
                viewModel.appendLog("Existing routes count: ${existingRoutes?.size ?: 0}")
                existingRoutes?.forEach { route ->
                    viewModel.appendLog("Existing route: ${route.name} (${route.id})")
                }

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