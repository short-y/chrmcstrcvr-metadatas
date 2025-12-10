package com.example.castkozt

import android.app.Application
import com.google.android.gms.cast.framework.CastContext
import com.google.android.gms.cast.framework.CastOptions
import com.google.android.gms.cast.framework.OptionsProvider
import com.google.android.gms.cast.framework.SessionProvider
import com.google.android.gms.cast.CastMediaControlIntent
import android.util.Log // Import Log for debugging

class KoztApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Enable verbose logging for Cast SDK
        CastContext.getSharedInstance(this).setLoggerLevel(Log.DEBUG)
        Log.d("KoztApp", "Cast SDK verbose logging enabled.")
    }
}
