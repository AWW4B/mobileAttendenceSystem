package com.edge.attendance.face

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.SystemClock
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.Closeable

/** Research timings, accumulated over a capture session. */
data class PipelineTimings(
    var photos: Int = 0,
    var faces: Int = 0,
    var detectMs: Long = 0,
    var embedMs: Long = 0,
    var matchMs: Long = 0,
)

/**
 * detect -> align -> embed, entirely on the phone. The photo bitmap and every
 * aligned crop are wiped as soon as they have been used.
 */
class FacePipeline(context: Context) : Closeable {
    private val detector = FaceDetector()
    private val embedderLazy = lazy { Embedder(context.applicationContext) }
    private val embedder by embedderLazy

    /** One vector per detected face, in detection order; [boxes] has the matching boxes. [onProgress] gets (stage, done, total). */
    suspend fun embeddings(
        photo: Bitmap, timings: PipelineTimings, boxes: MutableList<Rect>, onProgress: (String, Int, Int) -> Unit = { _, _, _ -> },
    ): List<FloatArray> {
        val t0 = SystemClock.elapsedRealtime()
        val faces = detector.detect(photo)
        val t1 = SystemClock.elapsedRealtime()
        onProgress("Detecting faces", faces.size, faces.size)
        boxes += faces.map { it.box }
        val vectors = withContext(Dispatchers.Default) {
            faces.mapIndexed { i, face ->
                val aligned = Aligner.align(photo, face.landmarks)
                try {
                    embedder.embed(aligned).also { onProgress("Matching", i + 1, faces.size) }
                } finally {
                    aligned.eraseColor(0)
                    aligned.recycle()
                }
            }
        }
        timings.photos += 1
        timings.faces += faces.size
        timings.detectMs += t1 - t0
        timings.embedMs += SystemClock.elapsedRealtime() - t1
        return vectors
    }

    override fun close() {
        detector.close()
        if (embedderLazy.isInitialized()) embedder.close()
    }
}
