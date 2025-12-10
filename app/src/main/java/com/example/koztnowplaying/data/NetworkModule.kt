package com.example.koztnowplaying.data

import com.example.koztnowplaying.network.ITunesApiService
import com.example.koztnowplaying.network.KoztApiService
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object NetworkModule {
    private val koztRetrofit = Retrofit.Builder()
        .baseUrl("https://api-nowplaying.amperwave.net/")
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    private val iTunesRetrofit = Retrofit.Builder()
        .baseUrl("https://itunes.apple.com/")
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val koztService: KoztApiService = koztRetrofit.create(KoztApiService::class.java)
    val iTunesService: ITunesApiService = iTunesRetrofit.create(ITunesApiService::class.java)
}
