plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.tonystakeontech.castkozt"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.tonystakeontech.castkozt"
        minSdk = 24
        targetSdk = 36
        versionCode = 7
        versionName = "1.6"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("KEYSTORE_PATH") ?: "upload-keystore.jks"
            storeFile = file(keystorePath)
            storePassword = System.getenv("KEYSTORE_PASSWORD") ?: "password"
            keyAlias = System.getenv("KEY_ALIAS") ?: "upload"
            keyPassword = System.getenv("KEY_PASSWORD") ?: "password"
        }
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.6"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    
    // Cast SDK
    implementation(libs.play.services.cast.framework)
    implementation(libs.androidx.mediarouter)
    implementation(libs.androidx.appcompat) // Required for Cast functionalities (MediRouteButton)
    implementation(libs.material)

    // Networking & JSON
    implementation(libs.retrofit)
    implementation(libs.converter.gson)
    implementation(libs.coil.compose)

    debugImplementation(libs.androidx.ui.tooling)
}
