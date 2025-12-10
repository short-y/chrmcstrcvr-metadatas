package com.example.koztnowplaying.data

import android.util.Log

data class TrackInfo(
    val title: String,
    val artist: String,
    val album: String,
    val imageUrl: String?
)

class KoztRepository {
    private val koztService = NetworkModule.koztService
    private val iTunesService = NetworkModule.iTunesService

    suspend fun fetchNowPlaying(): TrackInfo? {
        try {
            val response = koztService.getNowPlaying()
            val performance = response.performances?.firstOrNull()

            if (performance != null) {
                val title = performance.title?.trim() ?: "Unknown Song"
                val artist = performance.artist?.trim() ?: "Unknown Artist"
                val album = performance.album?.trim() ?: ""
                var imageUrl = performance.largeImage ?: performance.mediumImage ?: performance.smallImage

                if (imageUrl.isNullOrEmpty() && artist.isNotBlank() && title.isNotBlank()) {
                    imageUrl = fetchITunesArtwork(artist, title)
                }

                return TrackInfo(title, artist, album, imageUrl)
            }
        } catch (e: Exception) {
            Log.e("KoztRepository", "Error fetching KOZT data", e)
        }
        return null
    }

    private suspend fun fetchITunesArtwork(artist: String, title: String): String? {
        try {
            val term = "$artist $title"
            val response = iTunesService.searchMusic(term)
            val artworkUrl = response.results?.firstOrNull()?.artworkUrl100
            return artworkUrl?.replace("100x100bb", "600x600bb")
        } catch (e: Exception) {
            Log.e("KoztRepository", "Error fetching iTunes artwork", e)
        }
        return null
    }
}
