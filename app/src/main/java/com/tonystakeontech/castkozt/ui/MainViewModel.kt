package com.tonystakeontech.castkozt.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tonystakeontech.castkozt.data.KoztRepository
import com.tonystakeontech.castkozt.data.TrackInfo
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainViewModel : ViewModel() {
    private val repository = KoztRepository()

    private val _trackInfo = MutableStateFlow<TrackInfo?>(null)
    val trackInfo: StateFlow<TrackInfo?> = _trackInfo.asStateFlow()

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying.asStateFlow()

    private val _isNoStreamMode = MutableStateFlow(false)
    val isNoStreamMode: StateFlow<Boolean> = _isNoStreamMode.asStateFlow()

    private val _logs = MutableStateFlow<List<String>>(emptyList())
    val logs: StateFlow<List<String>> = _logs.asStateFlow()

    private val _resolvedStreamUrl = MutableStateFlow<String?>(null)
    val resolvedStreamUrl: StateFlow<String?> = _resolvedStreamUrl.asStateFlow()

    private val logDateFormat = SimpleDateFormat("HH:mm:ss", Locale.US)
    private val MAX_LOG_LINES = 50

    // Constants
    private val DEFAULT_STREAM_URL = "https://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u"

    // Track polling job for explicit cleanup
    private var pollingJob: Job? = null
    private var streamResolveJob: Job? = null

    init {
        appendLog("ViewModel initialized.")
        startPolling()
        resolveStream()
    }

    private fun resolveStream() {
        streamResolveJob = viewModelScope.launch {
            appendLog("Resolving stream URL from M3U...")
            val resolved = repository.resolveStreamUrl(DEFAULT_STREAM_URL)
            if (resolved != null) {
                _resolvedStreamUrl.value = resolved
                appendLog("Stream resolved: $resolved")
            } else {
                appendLog("Failed to resolve stream URL. Using default.")
                _resolvedStreamUrl.value = DEFAULT_STREAM_URL // Fallback
            }
        }
    }

    fun appendLog(message: String) {
        viewModelScope.launch {
            val timestamp = logDateFormat.format(Date())
            val newLogEntry = "$timestamp: $message"
            _logs.value = (_logs.value + newLogEntry).takeLast(MAX_LOG_LINES)
        }
    }

    private fun startPolling() {
        pollingJob = viewModelScope.launch {
            appendLog("Starting data polling.")
            while (isActive) { // Check if coroutine is still active
                try {
                    appendLog("Fetching now playing data...")
                    val info = repository.fetchNowPlaying()
                    if (info != null) {
                        _trackInfo.value = info
                        appendLog("Fetched: ${info.title} - ${info.artist}")
                    } else {
                        appendLog("No new track info.")
                    }
                    delay(15000) // Poll every 15 seconds
                } catch (e: Exception) {
                    if (isActive) {
                        appendLog("Error in polling: ${e.message}")
                    } else {
                        appendLog("Polling cancelled.")
                        break
                    }
                }
            }
            appendLog("Polling loop ended.")
        }
    }
    
    fun setPlaying(playing: Boolean) {
        _isPlaying.value = playing
    }

    fun toggleNoStreamMode() {
        _isNoStreamMode.value = !_isNoStreamMode.value
    }

    override fun onCleared() {
        super.onCleared()
        appendLog("ViewModel onCleared - cancelling background jobs.")

        // Cancel polling job
        pollingJob?.cancel()
        pollingJob = null

        // Cancel stream resolve job
        streamResolveJob?.cancel()
        streamResolveJob = null

        appendLog("ViewModel cleanup complete.")
    }
}
