package com.example.koztnowplaying.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.koztnowplaying.data.KoztRepository
import com.example.koztnowplaying.data.TrackInfo
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MainViewModel : ViewModel() {
    private val repository = KoztRepository()

    private val _trackInfo = MutableStateFlow<TrackInfo?>(null)
    val trackInfo: StateFlow<TrackInfo?> = _trackInfo.asStateFlow()

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying.asStateFlow()

    private val _isNoStreamMode = MutableStateFlow(false)
    val isNoStreamMode: StateFlow<Boolean> = _isNoStreamMode.asStateFlow()

    init {
        startPolling()
    }

    private fun startPolling() {
        viewModelScope.launch {
            while (true) {
                val info = repository.fetchNowPlaying()
                _trackInfo.value = info
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
