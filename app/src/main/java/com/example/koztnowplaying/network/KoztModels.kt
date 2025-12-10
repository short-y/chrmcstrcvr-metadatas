package com.example.koztnowplaying.network

import com.google.gson.annotations.SerializedName

data class KoztResponse(
    @SerializedName("performances") val performances: List<Performance>?
)

data class Performance(
    @SerializedName("title") val title: String?,
    @SerializedName("artist") val artist: String?,
    @SerializedName("album") val album: String?,
    @SerializedName("largeimage") val largeImage: String?,
    @SerializedName("mediumimage") val mediumImage: String?,
    @SerializedName("smallimage") val smallImage: String?
)
