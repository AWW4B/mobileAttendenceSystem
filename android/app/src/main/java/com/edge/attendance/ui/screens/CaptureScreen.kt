package com.edge.attendance.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.edge.attendance.R
import com.edge.attendance.ui.AttendanceViewModel
import com.edge.attendance.ui.CameraController
import com.edge.attendance.ui.CameraPreview
import com.edge.attendance.ui.Status
import com.edge.attendance.ui.UiState
import com.edge.attendance.ui.capture
import com.edge.attendance.ui.components.Glyph
import com.edge.attendance.ui.components.PrimaryButton
import com.edge.attendance.ui.components.pressScale
import com.edge.attendance.ui.theme.CameraColors
import com.edge.attendance.ui.theme.StatusBarIcons

/** Full-bleed camera. Always dark, like a camera app, in either theme. */
@Composable
fun CaptureScreen(state: UiState, vm: AttendanceViewModel) {
    val context = LocalContext.current
    var granted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    LaunchedEffect(Unit) { if (!granted) launcher.launch(Manifest.permission.CAMERA) }
    val controller = remember { CameraController() }
    StatusBarIcons(lightIcons = true)

    val matched = state.students.count { it.status == Status.PRESENT }
    val enrolled = state.students.count { it.status != Status.NOT_ENROLLED }

    Column(Modifier.fillMaxSize().background(CameraColors.Background).statusBarsPadding().navigationBarsPadding()) {
        Row(Modifier.fillMaxWidth().padding(end = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = vm::cancelSession) {
                Glyph(R.drawable.ic_arrow_left, tint = CameraColors.OnBackground, contentDescription = "Cancel and go back")
            }
            Text(
                state.section?.let { "${it.id} · ${it.title}" }.orEmpty(),
                style = MaterialTheme.typography.titleMedium, color = CameraColors.OnBackground, maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
        }
        Row(Modifier.padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 12.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            StatChip("Photos", state.photos.toString())
            StatChip("Faces", state.facesSeen.toString(), if (state.unknownFaces > 0) "· ${state.unknownFaces} unknown" else null)
            StatChip("Matched", "$matched/$enrolled")
        }
        Box(
            Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp)
                .clip(RoundedCornerShape(18.dp)).border(BorderStroke(1.dp, CameraColors.Hairline), RoundedCornerShape(18.dp))
                .drawWithContent { drawContent(); drawViewfinderCorners() },
        ) {
            if (granted) {
                CameraPreview(controller, Modifier.fillMaxSize())
            } else {
                Column(
                    Modifier.align(Alignment.Center).padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Text(
                        "Camera permission is needed to take attendance.",
                        style = MaterialTheme.typography.bodyLarge, color = CameraColors.OnBackground, textAlign = TextAlign.Center,
                    )
                    PrimaryButton("Allow camera", onClick = { launcher.launch(Manifest.permission.CAMERA) })
                }
            }
            if (state.busy) {
                Text(
                    "Matching faces on this phone",
                    modifier = Modifier.align(Alignment.TopCenter).padding(top = 20.dp)
                        .clip(RoundedCornerShape(8.dp)).background(CameraColors.Background.copy(alpha = 0.7f)).padding(horizontal = 12.dp, vertical = 6.dp),
                    style = MaterialTheme.typography.labelMedium, color = CameraColors.OnBackground,
                )
            }
            Text(
                "Photograph the whole class. Images stay in memory and are discarded after processing.",
                modifier = Modifier.align(Alignment.BottomCenter).padding(horizontal = 40.dp, vertical = 52.dp),
                style = MaterialTheme.typography.bodyMedium, color = CameraColors.Muted, textAlign = TextAlign.Center,
            )
        }
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 18.dp),
            horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.width(104.dp), contentAlignment = Alignment.CenterStart) {
                OutlinedButton(
                    onClick = vm::cancelSession, shape = RoundedCornerShape(12.dp), contentPadding = PaddingValues(horizontal = 16.dp),
                    border = BorderStroke(1.dp, Color(0x47EEF2ED)),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = CameraColors.OnBackground),
                ) { Text("Cancel", style = MaterialTheme.typography.labelLarge) }
            }
            Shutter(busy = state.busy, enabled = granted && !state.busy) {
                controller.capture(context, onPhoto = vm::onPhoto, onError = vm::showMessage)
            }
            Box(Modifier.width(104.dp), contentAlignment = Alignment.CenterEnd) {
                Button(
                    onClick = vm::toReview, enabled = state.photos > 0 && !state.busy, shape = RoundedCornerShape(12.dp),
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = CameraColors.OnBackground, contentColor = CameraColors.Background,
                        disabledContainerColor = CameraColors.Chip, disabledContentColor = CameraColors.Muted,
                    ),
                ) { Text("Review", style = MaterialTheme.typography.labelLarge) }
            }
        }
    }
}

@Composable
private fun StatChip(label: String, value: String, extra: String? = null) {
    Row(
        Modifier.clip(RoundedCornerShape(8.dp)).background(CameraColors.Chip).padding(horizontal = 9.dp, vertical = 5.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = CameraColors.Muted)
        Text(value, style = com.edge.attendance.ui.theme.MonoLabel, color = Color.White)
        if (extra != null) Text(extra, style = MaterialTheme.typography.labelMedium, color = CameraColors.Muted)
    }
}

@Composable
private fun Shutter(busy: Boolean, enabled: Boolean, onClick: () -> Unit) {
    val source = remember { MutableInteractionSource() }
    Box(
        Modifier.size(76.dp).pressScale(source, pressed = 0.95f)
            .border(3.dp, Color.White, CircleShape).padding(5.dp).clip(CircleShape)
            .background(if (busy) Color.Transparent else Color.White)
            .clickable(interactionSource = source, indication = null, enabled = enabled, role = Role.Button, onClickLabel = "Capture photo", onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (busy) CircularProgressIndicator(Modifier.size(28.dp), color = Color.White, strokeWidth = 3.dp)
    }
}

/** Four corner brackets: a viewfinder cue that costs no layout. */
private fun androidx.compose.ui.graphics.drawscope.ContentDrawScope.drawViewfinderCorners() {
    val len = 22.dp.toPx(); val inset = 16.dp.toPx(); val stroke = 2.dp.toPx()
    val color = Color(0x8CFFFFFF)
    fun corner(x: Float, y: Float, dx: Float, dy: Float) {
        drawLine(color, Offset(x, y), Offset(x + dx * len, y), stroke, StrokeCap.Round)
        drawLine(color, Offset(x, y), Offset(x, y + dy * len), stroke, StrokeCap.Round)
    }
    corner(inset, inset, 1f, 1f)
    corner(size.width - inset, inset, -1f, 1f)
    corner(inset, size.height - inset, 1f, -1f)
    corner(size.width - inset, size.height - inset, -1f, -1f)
}
