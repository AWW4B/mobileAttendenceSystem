package com.edge.attendance.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathMeasure
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import com.edge.attendance.ui.components.EVIDENCE_NOTE
import com.edge.attendance.ui.components.animatedCount
import com.edge.attendance.ui.theme.Motion
import com.edge.attendance.ui.theme.rememberReduceMotion
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.edge.attendance.R
import com.edge.attendance.ui.AttendanceViewModel
import com.edge.attendance.ui.UiState
import com.edge.attendance.ui.components.Glyph
import com.edge.attendance.ui.components.Hairline
import com.edge.attendance.ui.components.PrimaryButton
import com.edge.attendance.ui.theme.MonoBody

@Composable
fun DoneScreen(state: UiState, vm: AttendanceViewModel) {
    val cs = MaterialTheme.colorScheme
    val reduceMotion = rememberReduceMotion()
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 24.dp)) {
        Spacer(Modifier.height(56.dp))
        val draw = remember { Animatable(if (reduceMotion) 1f else 0f) }
        LaunchedEffect(Unit) { draw.animateTo(1f, tween(Motion.Slow, delayMillis = Motion.Base, easing = Motion.EaseOut)) }
        Box(
            Modifier.size(56.dp).clip(RoundedCornerShape(14.dp)).background(cs.primaryContainer),
            contentAlignment = Alignment.Center,
        ) {
            // The check strokes itself in once.
            Canvas(Modifier.size(28.dp)) {
                val path = Path().apply {
                    moveTo(size.width * 0.17f, size.height * 0.52f)
                    lineTo(size.width * 0.41f, size.height * 0.75f)
                    lineTo(size.width * 0.84f, size.height * 0.27f)
                }
                val seg = Path()
                PathMeasure().apply { setPath(path, false); getSegment(0f, length * draw.value, seg, true) }
                drawPath(seg, cs.primary, style = Stroke(2.25.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
        Spacer(Modifier.height(16.dp))
        Text("Attendance submitted", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(4.dp))
        Text(
            if (state.uploaded) "Recorded on the portal for ${state.section?.id.orEmpty()}."
            else "Verified by the campus server. The portal could not be reached, so this result will upload automatically.",
            style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant,
        )
        Spacer(Modifier.height(20.dp))
        Hairline()
        Column(Modifier.padding(vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Fact("Present", animatedCount(state.submittedPresent, from = 0).toString())
            Fact("Absent", animatedCount(state.submittedAbsent, from = 0).toString())
            Fact("Photos taken", state.submittedPhotos.toString())
        }
        Hairline()
        Spacer(Modifier.height(14.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Glyph(R.drawable.ic_lock, size = 18.dp, tint = cs.onSurfaceVariant)
            Text(
                "Face data for this session has been wiped from this phone. $EVIDENCE_NOTE",
                style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant,
            )
        }
        Spacer(Modifier.weight(1f))
        PrimaryButton("Back to sections", onClick = vm::backToSections, modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp))
    }
}

@Composable
private fun Fact(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MonoBody.copy(fontSize = MaterialTheme.typography.bodyLarge.fontSize))
    }
}
