package com.tonystakeontech.castkozt

import android.app.Application
import com.google.android.gms.cast.framework.CastContext

class KoztApp : Application() {
    override fun onCreate() {
        super.onCreate()
        try {
            CastContext.getSharedInstance(this)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}
