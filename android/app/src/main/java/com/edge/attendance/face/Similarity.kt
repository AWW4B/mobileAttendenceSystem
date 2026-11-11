package com.edge.attendance.face

/**
 * Closed-form least-squares similarity transform (rotation + uniform scale +
 * translation, no reflection). Identical to similarity_matrix() in
 * enrollment/face_pipeline.py; see models/model_contract.json.
 */
object Similarity {
    /** ArcFace 112x112 reference landmarks, contract order. */
    val REFERENCE = floatArrayOf(
        38.2946f, 51.6963f,
        73.5318f, 51.5014f,
        56.0252f, 71.7366f,
        41.5493f, 92.3655f,
        70.7299f, 92.2041f,
    )
    const val SIZE = 112

    /** Returns [a, b, tx, ty] with u = a*x - b*y + tx, v = b*x + a*y + ty. */
    fun estimate(src: FloatArray, dst: FloatArray = REFERENCE): DoubleArray {
        require(src.size == dst.size && src.size % 2 == 0 && src.size >= 4)
        val n = src.size / 2
        var msx = 0.0; var msy = 0.0; var mdx = 0.0; var mdy = 0.0
        for (i in 0 until n) {
            msx += src[2 * i]; msy += src[2 * i + 1]; mdx += dst[2 * i]; mdy += dst[2 * i + 1]
        }
        msx /= n; msy /= n; mdx /= n; mdy /= n
        var numA = 0.0; var numB = 0.0; var den = 0.0
        for (i in 0 until n) {
            val sx = src[2 * i] - msx; val sy = src[2 * i + 1] - msy
            val dx = dst[2 * i] - mdx; val dy = dst[2 * i + 1] - mdy
            numA += sx * dx + sy * dy
            numB += sx * dy - sy * dx
            den += sx * sx + sy * sy
        }
        require(den > 1e-9) { "degenerate landmarks" }
        val a = numA / den
        val b = numB / den
        return doubleArrayOf(a, b, mdx - (a * msx - b * msy), mdy - (b * msx + a * msy))
    }
}
