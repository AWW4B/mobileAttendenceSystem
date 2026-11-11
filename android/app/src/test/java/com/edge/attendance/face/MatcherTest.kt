package com.edge.attendance.face

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64
import kotlin.random.Random

class MatcherTest {
    private val dim = 512
    private val rnd = Random(7)

    private fun unit(seed: Int): FloatArray {
        val r = Random(seed)
        return Matcher.l2Normalize(FloatArray(dim) { r.nextFloat() * 2 - 1 })
    }

    private val perm = (0 until dim).shuffled(rnd).toIntArray()
    private val signs = FloatArray(dim) { if (rnd.nextBoolean()) 1f else -1f }

    /** What the MEC stores: t[i] = signs[i] * e[perm[i]]. */
    private fun stored(e: FloatArray) = FloatArray(dim) { i -> signs[i] * e[perm[i]] }

    private fun noisy(e: FloatArray, amount: Float, seed: Int): FloatArray {
        val r = Random(seed)
        return Matcher.l2Normalize(FloatArray(dim) { e[it] + amount * (r.nextFloat() * 2 - 1) })
    }

    @Test fun transformPreservesCosine() {
        val a = unit(1); val b = unit(2)
        val m = Matcher(emptyList(), perm, signs)
        assertEquals(Matcher.dot(a, b), Matcher.dot(m.transform(a), m.transform(b)), 1e-5f)
    }

    @Test fun matchesRightStudentsOneToOne() {
        val alice = unit(10); val bob = unit(11); val carol = unit(12)
        val m = Matcher(listOf("alice" to stored(alice), "bob" to stored(bob), "carol" to stored(carol)), perm, signs)
        val stranger = unit(99)
        val result = m.matchPhoto(listOf(noisy(bob, 0.02f, 1), noisy(alice, 0.02f, 2), stranger))
        val byId = result.matches.associateBy { it.pseudonym }
        assertEquals(setOf("alice", "bob"), byId.keys)
        assertTrue(byId.values.all { it.decision == Decision.PRESENT })
        assertEquals(1, result.unmatchedFaces)
    }

    @Test fun sameStudentTwiceInOnePhotoCountsOnce() {
        val alice = unit(10)
        val m = Matcher(listOf("alice" to stored(alice)), perm, signs)
        val result = m.matchPhoto(listOf(noisy(alice, 0.01f, 1), noisy(alice, 0.05f, 2)))
        assertEquals(1, result.matches.size)
        assertEquals(1, result.unmatchedFaces)
    }

    @Test fun decodeVectorReadsLittleEndianFloat32() {
        val v = floatArrayOf(0.5f, -1.25f, 3f)
        val buf = ByteBuffer.allocate(12).order(ByteOrder.LITTLE_ENDIAN)
        v.forEach { buf.putFloat(it) }
        assertArrayEquals(v, Matcher.decodeVector(Base64.getEncoder().encodeToString(buf.array())), 0f)
    }

    @Test fun wipeZeroesTemplates() {
        val t = stored(unit(3))
        Matcher(listOf("x" to t), perm, signs).wipe()
        assertTrue(t.all { it == 0f })
    }
}
