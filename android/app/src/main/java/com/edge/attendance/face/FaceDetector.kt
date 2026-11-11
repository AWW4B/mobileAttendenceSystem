package com.edge.attendance.face

import android.graphics.Bitmap
import android.graphics.PointF
import android.graphics.Rect
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.face.FaceLandmark
import kotlinx.coroutines.tasks.await
import java.io.Closeable
import kotlin.math.min

/** A face with its 5 landmarks in contract order (see models/model_contract.json). */
class DetectedFace(val box: Rect, val landmarks: FloatArray)

/**
 * ML Kit on-device detection. Runs fully offline (bundled model).
 *
 * Contract order is by IMAGE position: left eye, right eye, nose, left mouth
 * corner, right mouth corner. Sorting by x makes this independent of ML Kit's
 * subject-relative LEFT/RIGHT labels.
 *
 * Known deviation: ML Kit gives NOSE_BASE where the enrollment detector
 * (YuNet) gives the nose tip. The least-squares fit over 5 points keeps the
 * effect small; measure it in the research evaluation.
 */
class FaceDetector : Closeable {
    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
            .setMinFaceSize(0.03f) // class photos: faces are small
            .build()
    )

    suspend fun detect(bitmap: Bitmap): List<DetectedFace> {
        val faces = detector.process(InputImage.fromBitmap(bitmap, 0)).await()
        return faces.mapNotNull(::toContract)
            .filter { min(it.box.width(), it.box.height()) >= MIN_FACE_PX }
    }

    private fun toContract(face: Face): DetectedFace? {
        fun p(type: Int): PointF? = face.getLandmark(type)?.position
        val eyes = listOf(p(FaceLandmark.LEFT_EYE) ?: return null, p(FaceLandmark.RIGHT_EYE) ?: return null)
            .sortedBy { it.x }
        val nose = p(FaceLandmark.NOSE_BASE) ?: return null
        val mouth = listOf(p(FaceLandmark.MOUTH_LEFT) ?: return null, p(FaceLandmark.MOUTH_RIGHT) ?: return null)
            .sortedBy { it.x }
        return DetectedFace(
            face.boundingBox,
            floatArrayOf(
                eyes[0].x, eyes[0].y, eyes[1].x, eyes[1].y,
                nose.x, nose.y,
                mouth[0].x, mouth[0].y, mouth[1].x, mouth[1].y,
            ),
        )
    }

    override fun close() = detector.close()

    companion object {
        /** Smaller faces embed poorly. Enrollment uses 60 px; class photos need a bit lower. */
        const val MIN_FACE_PX = 48
    }
}
