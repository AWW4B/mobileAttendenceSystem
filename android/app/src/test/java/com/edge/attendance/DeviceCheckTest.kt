package com.edge.attendance

import org.junit.Assert.assertEquals
import org.junit.Test

class DeviceCheckTest {
    private val good = DeviceFacts(34, true, 8L shl 30, 8, 12_000_000L, true)
    private fun levels(f: DeviceFacts) = DeviceCheck.evaluate(f).map { it.level }

    @Test fun goodPhonePassesEverything() = assertEquals(List(6) { Level.PASS }, levels(good))

    @Test fun androidVersionThresholds() {
        assertEquals(Level.FAIL, levels(good.copy(sdk = 25))[0])
        assertEquals(Level.WARN, levels(good.copy(sdk = 28))[0])
        assertEquals(Level.PASS, levels(good.copy(sdk = 29))[0])
    }

    @Test fun ramThresholds() {
        assertEquals(Level.FAIL, levels(good.copy(ramBytes = 2L shl 30))[2])
        assertEquals(Level.WARN, levels(good.copy(ramBytes = 3L shl 30))[2])
        assertEquals(Level.PASS, levels(good.copy(ramBytes = 4L shl 30))[2])
    }

    @Test fun cameraThresholds() {
        assertEquals(Level.PASS, levels(good.copy(cameraPixels = 4000L * 3000))[4])
        assertEquals(Level.WARN, levels(good.copy(cameraPixels = 3264L * 2448))[4]) // 7.99 MP counts as 8
        assertEquals(Level.FAIL, levels(good.copy(cameraPixels = 2592L * 1944))[4])
        assertEquals(Level.FAIL, levels(good.copy(cameraPixels = null))[4])
    }

    @Test fun coresAutofocusAnd64Bit() {
        val l = levels(good.copy(cores = 4, continuousAf = false, has64Bit = false))
        assertEquals(listOf(Level.PASS, Level.FAIL, Level.PASS, Level.WARN, Level.PASS, Level.WARN), l)
    }
}
