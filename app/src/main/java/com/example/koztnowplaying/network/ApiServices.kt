package com.example.koztnowplaying.network

import retrofit2.http.GET
import retrofit2.http.Query

interface KoztApiService {
    @GET("api/v1/prtplus/nowplaying/10/4756/nowplaying.json")
    suspend fun getNowPlaying(): KoztResponse
}

interface ITunesApiService {
    @GET("search")
    suspend fun searchMusic(
        @Query("term") term: String,
        @Query("media") media: String = "music",
        @Query("limit") limit: Int = 1
    ): ITunesResponse
}
