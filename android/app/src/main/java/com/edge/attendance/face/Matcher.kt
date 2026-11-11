package com.edge.attendance.face

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64
import kotlin.math.sqrt

enum class Decision { PRESENT, REVIEW }

data class Match(val pseudonym: String, val score: Float, val decision: Decision)

data class PhotoResult(val matches: List<Match>, val unmatchedFaces: Int)

/**
 * On-device one-to-many matching against one section's templates.
 *
 * Templates arrive from the MEC already transformed (t[i] = signs[i] * e[perm[i]]);
 * live embeddings get the same transform, so cosine similarity is unchanged.
 * Thresholds come from models/model_contract.json and should be re-tuned on
 * real class photos.
 */
class Matcher(
    templates: List<Pair<String, FloatArray>>,
    private val permutation: IntArray,
    private val signs: FloatArray,
    private val accept: Float = ACCEPT,
    private val review: Float = REVIEW,
) {
    private val ids = templates.map { it.first }
    private val vectors = templates.map { it.second }

    init {
        require(permutation.size == signs.size) { "transform size mismatch" }
        vectors.forEach { require(it.size == permutation.size) { "template size mismatch" } }
    }

    val size: Int get() = ids.size

    fun transform(q: FloatArray): FloatArray = FloatArray(q.size) { i -> signs[i] * q[permutation[i]] }

    /**
     * Match all faces found in ONE photo. Assignment is one-to-one (a face
     * gets at most one student, a student at most one face), greedy by score.
     */
    fun matchPhoto(faces: List<FloatArray>): PhotoResult {
        data class Candidate(val face: Int, val template: Int, val score: Float)

        val candidates = ArrayList<Candidate>()
        faces.forEachIndexed { fi, q ->
            val t = transform(q)
            vectors.forEachIndexed { ti, v ->
                val s = dot(t, v)
                if (s >= review) candidates += Candidate(fi, ti, s)
            }
            t.fill(0f)
        }
        candidates.sortByDescending { it.score }
        val usedFaces = HashSet<Int>()
        val usedTemplates = HashSet<Int>()
        val matches = ArrayList<Match>()
        for (c in candidates) {
            if (c.face in usedFaces || c.template in usedTemplates) continue
            usedFaces += c.face
            usedTemplates += c.template
            matches += Match(ids[c.template], c.score, if (c.score >= accept) Decision.PRESENT else Decision.REVIEW)
        }
        return PhotoResult(matches, faces.size - usedFaces.size)
    }

    /** Overwrite template memory when the session ends. */
    fun wipe() = vectors.forEach { it.fill(0f) }

    companion object {
        const val ACCEPT = 0.40f
        const val REVIEW = 0.30f

        fun dot(a: FloatArray, b: FloatArray): Float {
            var s = 0f
            for (i in a.indices) s += a[i] * b[i]
            return s
        }

        fun l2Normalize(v: FloatArray): FloatArray {
            var n = 0f
            for (x in v) n += x * x
            val norm = sqrt(n)
            require(norm > 1e-6f) { "zero-norm embedding" }
            return FloatArray(v.size) { v[it] / norm }
        }

        /** MEC wire format: base64 of float32 little-endian. */
        fun decodeVector(b64: String): FloatArray {
            val bytes = Base64.getDecoder().decode(b64)
            val buf = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
            return FloatArray(buf.remaining()).also { buf.get(it) }.also { bytes.fill(0) }
        }
    }
}
