import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// The face model and the MEC's TLS certificate are not committed. They are
// copied in from the repo at build time:
//   ../models/w600k_mbf.onnx         (enrollment/fetch_models.py)   required
//   ../server/data/tls/cert.pem      (server/scripts/gen_dev_cert.py) optional, pinned if present
val repoRoot = rootProject.projectDir.parentFile
val modelFile = File(repoRoot, "models/w600k_mbf.onnx")
val certFile = File(repoRoot, "server/data/tls/cert.pem")
val edgeAssetsDir = layout.buildDirectory.dir("generated/edgeAssets")

val copyEdgeAssets by tasks.registering(Copy::class) {
    doFirst {
        if (!modelFile.exists()) {
            throw GradleException("Missing $modelFile. Run `python enrollment/fetch_models.py` from the repo root first.")
        }
        if (!certFile.exists()) {
            logger.warn("No $certFile: the app will only trust system CAs. Run server/scripts/gen_dev_cert.py.")
        }
    }
    from(modelFile)
    if (certFile.exists()) from(certFile) { rename { "mec_cert.pem" } }
    into(edgeAssetsDir)
}

android {
    namespace = "com.edge.attendance"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.edge.attendance"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
    }
    sourceSets["main"].assets.srcDir(edgeAssetsDir)
    androidResources {
        noCompress += "onnx"
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

tasks.named("preBuild") { dependsOn(copyEdgeAssets) }

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)

    implementation(libs.camerax.core)
    implementation(libs.camerax.camera2)
    implementation(libs.camerax.lifecycle)
    implementation(libs.camerax.view)
    implementation(libs.mlkit.face)
    implementation(libs.onnxruntime.android)

    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.play.services)
    implementation(libs.androidx.work.runtime)

    testImplementation(libs.junit)
}
