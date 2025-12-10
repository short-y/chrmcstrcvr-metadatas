package com.example.koztnowplaying.network

import com.google.gson.annotations.SerializedName

data class ITunesResponse(
    @SerializedName("resultCount") val resultCount: Int,
    @SerializedName("results") val results: List<ITunesResult>?
)

data class ITunesResult(
    @SerializedName("artworkUrl100") val artworkUrl100: String?
)
