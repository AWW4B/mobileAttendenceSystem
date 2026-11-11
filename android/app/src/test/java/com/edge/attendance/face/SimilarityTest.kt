package com.edge.attendance.face

import org.junit.Assert.assertEquals
import org.junit.Test
import kotlin.math.cos
import kotlin.math.sin

class SimilarityTest {
    @Test fun recoversKnownTransform() {
        // Same case as enrollment/test_face_pipeline.py::test_similarity_matrix_recovers_known_transform
        val angle = 0.3; val scale = 1.7; val tx = 12.0; val ty = -5.0
        val a = scale * cos(angle); val b = scale * sin(angle)
        val src = Similarity.REFERENCE
        val dst = FloatArray(src.size)
        for (i in 0 until src.size / 2) {
            val x = src[2 * i].toDouble(); val y = src[2 * i + 1].toDouble()
            dst[2 * i] = (a * x - b * y + tx).toFloat()
            dst[2 * i + 1] = (b * x + a * y + ty).toFloat()
        }
        val m = Similarity.estimate(src, dst)
        assertEquals(a, m[0], 1e-4); assertEquals(b, m[1], 1e-4)
        assertEquals(tx, m[2], 1e-3); assertEquals(ty, m[3], 1e-3)
    }

    @Test fun referenceMapsToItself() {
        val m = Similarity.estimate(Similarity.REFERENCE)
        assertEquals(1.0, m[0], 1e-6); assertEquals(0.0, m[1], 1e-6)
        assertEquals(0.0, m[2], 1e-4); assertEquals(0.0, m[3], 1e-4)
    }
}
