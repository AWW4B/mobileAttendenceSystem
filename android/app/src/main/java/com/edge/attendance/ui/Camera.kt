package com.edge.attendance.ui

import android.graphics.Bitmap
import android.graphics.Matrix
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner

/** Lets the capture button reach the bound ImageCapture use case. */
class CameraController {
    internal var imageCapture: ImageCapture? = null
}

/**
 * Back-camera preview. Photos are captured into memory only
 * (OnImageCapturedCallback): nothing is written to storage or the gallery.
 */
@Composable
fun CameraPreview(controller: CameraController, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember { PreviewView(context) }

    DisposableEffect(lifecycleOwner) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
            val capture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                .build()
            provider.unbindAll()
            provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, capture)
            controller.imageCapture = capture
        }, ContextCompat.getMainExecutor(context))
        onDispose {
            controller.imageCapture = null
            if (future.isDone) future.get().unbindAll()
        }
    }
    AndroidView(factory = { previewView }, modifier = modifier)
}

fun CameraController.capture(context: android.content.Context, onPhoto: (Bitmap) -> Unit, onError: (String) -> Unit) {
    val capture = imageCapture ?: return onError("Camera not ready")
    capture.takePicture(ContextCompat.getMainExecutor(context), object : ImageCapture.OnImageCapturedCallback() {
        override fun onCaptureSuccess(image: ImageProxy) {
            val bitmap = try {
                image.toUprightBitmap()
            } finally {
                image.close()
            }
            onPhoto(bitmap)
        }

        override fun onError(exception: ImageCaptureException) {
            Log.w("Camera", "capture failed", exception)
            onError("Capture failed: ${exception.message}")
        }
    })
}

private fun ImageProxy.toUprightBitmap(): Bitmap {
    val source = toBitmap()
    val degrees = imageInfo.rotationDegrees
    if (degrees == 0) return source
    val rotated = Bitmap.createBitmap(source, 0, 0, source.width, source.height,
        Matrix().apply { postRotate(degrees.toFloat()) }, true)
    if (rotated !== source) {
        source.eraseColor(0)
        source.recycle()
    }
    return rotated
}
