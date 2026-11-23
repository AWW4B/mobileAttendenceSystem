package com.edge.attendance

import android.app.ActivityManager
import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.os.Build
import kotlin.math.roundToInt

enum class Level { PASS, WARN, FAIL }

data class Check(val label: String, val value: String, val level: Level)

/** Raw measurements; the only part that touches Android APIs is [measure]. */
data class DeviceFacts(
    val sdk: Int, val has64Bit: Boolean, val ramBytes: Long, val cores: Int,
    val cameraPixels: Long?, // largest rear JPEG output, null = no rear camera
    val continuousAf: Boolean,
)

object DeviceCheck {
    private const val GIB = 1024.0 * 1024 * 1024

    /** Pure threshold logic (unit tested). */
    fun evaluate(f: DeviceFacts): List<Check> {
        val ram = f.ramBytes / GIB
        val mp = f.cameraPixels?.let { (it / 1e5).roundToInt() / 10.0 } // 3264x2448 = 7.99 -> 8.0
        return listOf(
            Check("Android version", "API ${f.sdk}", if (f.sdk < 26) Level.FAIL else if (f.sdk < 29) Level.WARN else Level.PASS),
            Check("64-bit", if (f.has64Bit) "Yes" else "No", if (f.has64Bit) Level.PASS else Level.FAIL),
            Check("Memory", "%.1f GB".format(ram), if (ram < 3) Level.FAIL else if (ram < 4) Level.WARN else Level.PASS),
            Check("CPU cores", f.cores.toString(), if (f.cores < 6) Level.WARN else Level.PASS),
            Check("Rear camera", mp?.let { "$it MP" } ?: "None", when {
                mp == null || mp < 8 -> Level.FAIL
                mp < 12 -> Level.WARN
                else -> Level.PASS
            }),
            Check("Autofocus", if (f.continuousAf) "Continuous" else "Limited", if (f.continuousAf) Level.PASS else Level.WARN),
        )
    }

    fun run(context: Context): List<Check> = evaluate(measure(context))

    private fun measure(context: Context): DeviceFacts {
        val mem = ActivityManager.MemoryInfo()
        context.getSystemService(ActivityManager::class.java).getMemoryInfo(mem)
        val cm = context.getSystemService(CameraManager::class.java)
        val rear = try {
            cm.cameraIdList.map { cm.getCameraCharacteristics(it) }
                .firstOrNull { it.get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK }
        } catch (e: Exception) { null }
        val pixels = rear?.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
            ?.getOutputSizes(ImageFormat.JPEG)?.maxOfOrNull { it.width.toLong() * it.height }
        val af = rear?.get(CameraCharacteristics.CONTROL_AF_AVAILABLE_MODES)
            ?.contains(CameraCharacteristics.CONTROL_AF_MODE_CONTINUOUS_PICTURE) == true
        return DeviceFacts(
            Build.VERSION.SDK_INT, Build.SUPPORTED_64_BIT_ABIS.isNotEmpty(), mem.totalMem,
            Runtime.getRuntime().availableProcessors(), pixels, af,
        )
    }
}
