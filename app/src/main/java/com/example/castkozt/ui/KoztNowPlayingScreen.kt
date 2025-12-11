package com.example.castkozt.ui

import androidx.appcompat.view.ContextThemeWrapper
import androidx.appcompat.R as AppCompatR
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.vectorResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.mediarouter.app.MediaRouteButton
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.example.castkozt.R
import com.example.castkozt.data.TrackInfo
import com.google.android.gms.cast.framework.CastButtonFactory
import com.google.android.gms.cast.CastMediaControlIntent // Keep this as it's used in the selector


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun KoztNowPlayingScreen(
    trackInfo: TrackInfo?,
    isNoStreamMode: Boolean,
    onToggleNoStreamMode: () -> Unit,
    logs: List<String> // New parameter for debug logs
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Cast KOZT") }, // Changed title
                actions = {
                    CastButton()
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Album Art
            Card(
                modifier = Modifier
                    .size(300.dp)
                    .clip(RoundedCornerShape(16.dp)),
                elevation = CardDefaults.cardElevation(8.dp)
            ) {
                if (trackInfo?.imageUrl != null) {
                    AsyncImage(
                        model = ImageRequest.Builder(LocalContext.current)
                            .data(trackInfo.imageUrl)
                            .crossfade(true)
                            .build(),
                        contentDescription = "Album Art",
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    // Placeholder (can be a local resource or solid color)
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.Gray),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("No Image", color = Color.White)
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Text Info
            Text(
                text = trackInfo?.title ?: "Waiting for data...",
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = trackInfo?.artist ?: "",
                fontSize = 18.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = trackInfo?.album ?: "",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Controls
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("No-Stream Mode (Metadata Only)")
                Switch(
                    checked = isNoStreamMode,
                    onCheckedChange = { onToggleNoStreamMode() },
                    modifier = Modifier.padding(start = 8.dp)
                )
            }
            
            // Debug Logs Section
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Debug Log:",
                fontWeight = FontWeight.Bold,
                modifier = Modifier.align(Alignment.Start)
            )
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(150.dp)
                    .background(Color.Black.copy(alpha = 0.8f))
                    .padding(8.dp)
            ) {
                items(logs) { log ->
                    Text(text = log, color = Color.Green, fontSize = 10.sp)
                }
            }
        }
    }
}

@Composable
fun CastButton() {
    AndroidView(
        modifier = Modifier
            .size(48.dp) // Ensure explicit size
            .background(Color.White.copy(alpha = 0.2f), shape = RoundedCornerShape(24.dp)), // Visible touch target
        factory = { context ->
            val contextWrapper = ContextThemeWrapper(context, AppCompatR.style.Theme_AppCompat_Light_DarkActionBar) // Use this theme for a dark icon
            MediaRouteButton(contextWrapper).apply {
                CastButtonFactory.setUpMediaRouteButton(context.applicationContext, this)
                
                // Manually broaden the selector to ensure it shows for ANY Cast device
                val selector = androidx.mediarouter.media.MediaRouteSelector.Builder()
                    .addControlCategory(CastMediaControlIntent.categoryForCast(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID))
                    .addControlCategory("com.google.android.gms.cast.CATEGORY_CAST")
                    .build()
                this.routeSelector = selector
                
                // FORCE VISIBILITY even if it thinks no devices are found
                this.setAlwaysVisible(true)
            }
        }
    )
}
