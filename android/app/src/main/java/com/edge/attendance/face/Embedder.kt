package com.edge.attendance.face

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import java.io.Closeable
import java.nio.FloatBuffer

/** Warps a face to the 112x112 contract layout. */
object Aligner {
    fun align(source: Bitmap, landmarks: FloatArray): Bitmap {
        val (a, b, tx, ty) = Similarity.estimate(landmarks)
        val matrix = Matrix().apply {
            setValues(floatArrayOf(
                a.toFloat(), (-b).toFloat(), tx.toFloat(),
                b.toFloat(), a.toFloat(), ty.toFloat(),
                0f, 0f, 1f,
            ))
        }
        val out = Bitmap.createBitmap(Similarity.SIZE, Similarity.SIZE, Bitmap.Config.ARGB_8888)
        Canvas(out).apply {
            drawColor(Color.BLACK)
            drawBitmap(source, matrix, Paint(Paint.FILTER_BITMAP_FLAG)) // bilinear
        }
        return out
    }
}

/**
 * MobileFaceNet (w600k_mbf.onnx) via ONNX Runtime: the same model file the
 * laptop uses at enrollment. Input [1,3,112,112] RGB, (x-127.5)/127.5;
 * output 512-d, L2-normalised. Not thread-safe (reuses buffers).
 */
class Embedder(context: Context) : Closeable {
    private val env = OrtEnvironment.getEnvironment()
    private val session: OrtSession = env.createSession(
        context.assets.open(MODEL_ASSET).use { it.readBytes() },
        OrtSession.SessionOptions().apply { setIntraOpNumThreads(4) },
    )
    private val inputName = session.inputNames.first()
    private val pixels = IntArray(PLANE)
    private val input = FloatArray(3 * PLANE)

    fun embed(aligned: Bitmap): FloatArray {
        require(aligned.width == Similarity.SIZE && aligned.height == Similarity.SIZE)
        aligned.getPixels(pixels, 0, Similarity.SIZE, 0, 0, Similarity.SIZE, Similarity.SIZE)
        for (i in 0 until PLANE) {
            val p = pixels[i]
            input[i] = (((p shr 16) and 0xFF) - 127.5f) / 127.5f            // R
            input[PLANE + i] = (((p shr 8) and 0xFF) - 127.5f) / 127.5f     // G
            input[2 * PLANE + i] = ((p and 0xFF) - 127.5f) / 127.5f         // B
        }
        val raw = try {
            OnnxTensor.createTensor(env, FloatBuffer.wrap(input), SHAPE).use { tensor ->
                session.run(mapOf(inputName to tensor)).use { result ->
                    @Suppress("UNCHECKED_CAST")
                    (result.get(0).value as Array<FloatArray>)[0].copyOf()
                }
            }
        } finally {
            pixels.fill(0)
            input.fill(0f)
        }
        check(raw.size == DIM) { "model produced ${raw.size} dims, contract says $DIM" }
        return Matcher.l2Normalize(raw).also { raw.fill(0f) }
    }

    override fun close() = session.close()

    companion object {
        const val MODEL_ASSET = "w600k_mbf.onnx"
        const val DIM = 512
        private const val PLANE = Similarity.SIZE * Similarity.SIZE
        private val SHAPE = longArrayOf(1, 3, Similarity.SIZE.toLong(), Similarity.SIZE.toLong())
    }
}
