package com.example.castkozt.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.castkozt.data.KoztRepository
import com.example.castkozt.data.TrackInfo
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
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

    private val logDateFormat = SimpleDateFormat("HH:mm:ss", Locale.US)
    private val MAX_LOG_LINES = 50

    init {
        appendLog("ViewModel initialized.")
        startPolling()
    }

    fun appendLog(message: String) {
        viewModelScope.launch {
            val timestamp = logDateFormat.format(Date())
            val newLogEntry = "$timestamp: $message"
            _logs.value = (_logs.value + newLogEntry).takeLast(MAX_LOG_LINES)
        }
    }

    private fun startPolling() {
        viewModelScope.launch {
            appendLog("Starting data polling.")
            while (true) {
                appendLog("Fetching now playing data...")
                val info = repository.fetchNowPlaying()
                if (info != null) {
                    _trackInfo.value = info
                    appendLog("Fetched: ${info.title} - ${info.artist}")
                } else {
                    appendLog("No new track info.")
                }
                delay(15000) // Poll every 15 seconds
            }
        }
    }
    
    fun setPlaying(playing: Boolean) {
        _isPlaying.value = playing
    }

    fun toggleNoStreamMode() {
        _isNoStreamMode.value = !_isNoStreamMode.value
    }
}
