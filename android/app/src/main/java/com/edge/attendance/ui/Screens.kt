package com.edge.attendance.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.edge.attendance.data.Section

@Composable
fun AttendanceApp(vm: AttendanceViewModel) {
    val colors = if (isSystemInDarkTheme()) darkColorScheme() else lightColorScheme()
    MaterialTheme(colorScheme = colors) {
        val state by vm.state.collectAsStateWithLifecycle()
        Surface(Modifier.fillMaxSize()) {
            Box(Modifier.safeDrawingPadding()) {
                when (state.screen) {
                    Screen.LOGIN -> LoginScreen(state, vm)
                    Screen.SECTIONS -> SectionsScreen(state, vm)
                    Screen.CAPTURE -> CaptureScreen(state, vm)
                    Screen.REVIEW -> ReviewScreen(state, vm)
                    Screen.DONE -> DoneScreen(state, vm)
                }
                if (state.busy) {
                    Box(Modifier.fillMaxSize().background(Color(0x66000000)), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                state.message?.let { msg ->
                    AlertDialog(
                        onDismissRequest = vm::dismissMessage,
                        confirmButton = { TextButton(onClick = vm::dismissMessage) { Text("OK") } },
                        text = { Text(msg) },
                    )
                }
            }
        }
    }
}

// ---- Login --------------------------------------------------------------------
@Composable
private fun LoginScreen(state: UiState, vm: AttendanceViewModel) {
    var username by rememberSaveable { mutableStateOf(state.lastUsername) }
    var password by rememberSaveable { mutableStateOf("") }
    var portalUrl by rememberSaveable { mutableStateOf(state.portalUrl) }
    var mecUrl by rememberSaveable { mutableStateOf(state.mecUrl) }
    var showServers by rememberSaveable { mutableStateOf(false) }

    LazyColumn(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text("Edge Attendance", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("Faces are recognised on this phone. Photos never leave it.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        item {
            OutlinedTextField(username, { username = it }, Modifier.fillMaxWidth(), label = { Text("Username") },
                singleLine = true)
        }
        item {
            OutlinedTextField(password, { password = it }, Modifier.fillMaxWidth(), label = { Text("Password") },
                singleLine = true, visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
        }
        item {
            TextButton(onClick = { showServers = !showServers }) {
                Text(if (showServers) "Hide server settings" else "Server settings")
            }
        }
        if (showServers) {
            item {
                OutlinedTextField(portalUrl, { portalUrl = it }, Modifier.fillMaxWidth(),
                    label = { Text("Portal URL") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
            }
            item {
                OutlinedTextField(mecUrl, { mecUrl = it }, Modifier.fillMaxWidth(),
                    label = { Text("Campus MEC URL") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
            }
        }
        item {
            Button(
                onClick = { vm.login(username, password, portalUrl, mecUrl); password = "" },
                enabled = username.isNotBlank() && password.isNotBlank() && !state.busy,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Sign in") }
        }
    }
}

// ---- Sections -----------------------------------------------------------------
@Composable
private fun SectionsScreen(state: UiState, vm: AttendanceViewModel) {
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Your sections", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(state.teacherName.orEmpty(), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            TextButton(onClick = vm::refreshSections) { Text("Refresh") }
            TextButton(onClick = vm::logout) { Text("Log out") }
        }
        Spacer(Modifier.height(12.dp))
        if (state.sections.isEmpty()) {
            Text("No sections assigned to you yet.")
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.sections, key = Section::id) { s ->
                Card(Modifier.fillMaxWidth().clickable(enabled = !state.busy) { vm.startSession(s) }) {
                    Column(Modifier.padding(16.dp)) {
                        Text("${s.id} · ${s.title}", fontWeight = FontWeight.SemiBold)
                        Text("${s.student_count} students · tap to take attendance",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

// ---- Capture ------------------------------------------------------------------
@Composable
private fun CaptureScreen(state: UiState, vm: AttendanceViewModel) {
    val context = LocalContext.current
    var granted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    LaunchedEffect(Unit) { if (!granted) launcher.launch(Manifest.permission.CAMERA) }
    val controller = remember { CameraController() }
    val present = state.students.count { it.status == Status.PRESENT }
    val enrolled = state.students.count { it.status != Status.NOT_ENROLLED }

    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(16.dp)) {
            Text(state.section?.let { "${it.id} · ${it.title}" }.orEmpty(), fontWeight = FontWeight.SemiBold)
            Text("Photos: ${state.photos} · Faces: ${state.facesSeen} · Recognised: $present/$enrolled · Unknown faces: ${state.unknownFaces}",
                style = MaterialTheme.typography.bodySmall)
            Text("Take one or more photos covering the whole class. Images stay in memory and are discarded after processing.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (granted) {
                CameraPreview(controller, Modifier.fillMaxSize())
            } else {
                Column(Modifier.align(Alignment.Center).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("Camera permission is needed to take attendance.")
                    Button(onClick = { launcher.launch(Manifest.permission.CAMERA) }) { Text("Allow camera") }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = vm::cancelSession, enabled = !state.busy) { Text("Cancel") }
            Button(
                onClick = {
                    controller.capture(context, onPhoto = vm::onPhoto, onError = vm::showMessage)
                },
                enabled = granted && !state.busy,
                modifier = Modifier.weight(1f),
            ) { Text("Capture") }
            Button(onClick = vm::toReview, enabled = state.photos > 0 && !state.busy) { Text("Review") }
        }
    }
}

// ---- Review -------------------------------------------------------------------
@Composable
private fun ReviewScreen(state: UiState, vm: AttendanceViewModel) {
    val marked = state.students.count { it.markedPresent }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Review attendance", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("$marked of ${state.students.size} marked present. Check the amber rows; tick or untick to correct.",
            style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(8.dp))
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            items(state.students, key = StudentRow::pseudonym) { s ->
                Row(
                    Modifier.fillMaxWidth().clickable(enabled = s.status != Status.NOT_ENROLLED) {
                        vm.setPresent(s.pseudonym, !s.markedPresent)
                    }.padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Checkbox(checked = s.markedPresent, enabled = s.status != Status.NOT_ENROLLED,
                        onCheckedChange = { vm.setPresent(s.pseudonym, it) })
                    Column(Modifier.weight(1f)) {
                        Text(s.name, fontWeight = FontWeight.Medium)
                        Text(s.rollNo, style = MaterialTheme.typography.bodySmall)
                    }
                    StatusChip(s)
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = vm::backToCapture, enabled = !state.busy) { Text("More photos") }
            Button(onClick = vm::submit, enabled = !state.busy, modifier = Modifier.weight(1f)) { Text("Submit") }
        }
    }
}

@Composable
private fun StatusChip(s: StudentRow) {
    val (label, color) = when (s.status) {
        Status.PRESENT -> "Matched ${pct(s.score)}" to Color(0xFF1F8A4C)
        Status.REVIEW -> "Check ${pct(s.score)}" to Color(0xFFB7791F)
        Status.ABSENT -> "Not seen" to Color(0xFF8A8A8A)
        Status.NOT_ENROLLED -> "No face on file" to Color(0xFF8A8A8A)
    }
    Box(Modifier.background(color.copy(alpha = 0.15f), RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 2.dp)) {
        Text(label, color = color, style = MaterialTheme.typography.labelMedium)
    }
}

private fun pct(score: Float?) = score?.let { "${(it * 100).toInt()}%" }.orEmpty()

// ---- Done ---------------------------------------------------------------------
@Composable
private fun DoneScreen(state: UiState, vm: AttendanceViewModel) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.size(56.dp).background(Color(0xFF1F8A4C), RoundedCornerShape(28.dp)), contentAlignment = Alignment.Center) {
            Text("✓", color = Color.White, style = MaterialTheme.typography.headlineMedium)
        }
        Spacer(Modifier.height(16.dp))
        Text("Attendance submitted", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text(state.result.orEmpty())
        Spacer(Modifier.height(8.dp))
        Text("Face data for this session has been wiped from the phone.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(24.dp))
        Button(onClick = vm::backToSections) { Text("Back to sections") }
    }
}
