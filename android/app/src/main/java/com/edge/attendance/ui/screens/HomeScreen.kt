package com.edge.attendance.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.edge.attendance.R
import com.edge.attendance.data.Section
import com.edge.attendance.ui.AttendanceViewModel
import com.edge.attendance.ui.Tab
import com.edge.attendance.ui.UiState
import com.edge.attendance.ui.components.ChipKind
import com.edge.attendance.ui.components.EmptyState
import com.edge.attendance.ui.components.Glyph
import com.edge.attendance.ui.components.GroupHeader
import com.edge.attendance.ui.components.Hairline
import com.edge.attendance.ui.components.ListSurface
import com.edge.attendance.ui.components.ScreenHeader
import com.edge.attendance.ui.components.SecondaryButton
import com.edge.attendance.ui.components.StatusChip
import com.edge.attendance.ui.components.TonalButton
import com.edge.attendance.ui.theme.MonoBody

/** Bottom bar height the snackbar host has to clear. */
val NavBarHeight = 80.dp

@Composable
fun HomeScreen(state: UiState, vm: AttendanceViewModel) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = { EdgeNavigationBar(state, vm) },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when (state.tab) {
                Tab.SECTIONS -> SectionsTab(state, vm)
                Tab.UPLOADS -> UploadsTab(state, vm)
                Tab.DEVICE -> DeviceTab(state, vm)
            }
        }
    }
}

@Composable
private fun EdgeNavigationBar(state: UiState, vm: AttendanceViewModel) {
    val cs = MaterialTheme.colorScheme
    val colors = NavigationBarItemDefaults.colors(
        selectedIconColor = cs.primary, selectedTextColor = cs.onSurface, indicatorColor = cs.primaryContainer,
        unselectedIconColor = cs.secondary, unselectedTextColor = cs.secondary,
    )
    Column {
        Hairline()
        NavigationBar(containerColor = cs.surfaceContainer, tonalElevation = 0.dp) {
            NavigationBarItem(
                selected = state.tab == Tab.SECTIONS, onClick = { vm.setTab(Tab.SECTIONS) }, colors = colors,
                icon = { Glyph(R.drawable.ic_sections) }, label = { Text("Sections", style = MaterialTheme.typography.labelMedium) },
            )
            NavigationBarItem(
                selected = state.tab == Tab.UPLOADS, onClick = { vm.setTab(Tab.UPLOADS) }, colors = colors,
                icon = {
                    BadgedBox(badge = { if (state.pendingUploads > 0) Badge(containerColor = cs.tertiary) }) { Glyph(R.drawable.ic_cloud_up) }
                },
                label = { Text("Uploads", style = MaterialTheme.typography.labelMedium) },
            )
            NavigationBarItem(
                selected = state.tab == Tab.DEVICE, onClick = { vm.setTab(Tab.DEVICE) }, colors = colors,
                icon = { Glyph(R.drawable.ic_device) }, label = { Text("Device", style = MaterialTheme.typography.labelMedium) },
            )
        }
    }
}

// ---- Sections ---------------------------------------------------------------
@Composable
private fun SectionsTab(state: UiState, vm: AttendanceViewModel) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item {
            ScreenHeader("Sections", state.teacherName) {
                IconButton(onClick = vm::refreshSections, enabled = !state.busy) {
                    Glyph(R.drawable.ic_refresh, contentDescription = "Refresh sections", tint = MaterialTheme.colorScheme.secondary)
                }
            }
        }
        if (state.pendingUploads > 0) item { PendingBanner(state.pendingUploads) { vm.setTab(Tab.UPLOADS) } }
        if (state.sections.isEmpty()) {
            item {
                EmptyState(
                    R.drawable.ic_sections, "No sections assigned yet",
                    "Sections are assigned by an administrator. Use refresh once yours appear.",
                )
            }
        } else {
            item { GroupHeader("Choose a section", state.sections.size) }
            item { Hairline() }
            items(state.sections, key = Section::id) { s ->
                SectionRow(s, enabled = !state.busy) { vm.startSession(s) }
                Hairline()
            }
        }
    }
}

@Composable
private fun PendingBanner(count: Int, onView: () -> Unit) {
    val cs = MaterialTheme.colorScheme
    Surface(
        color = cs.tertiaryContainer, shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, bottom = 12.dp),
    ) {
        Row(Modifier.padding(start = 14.dp, end = 4.dp, top = 4.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Glyph(R.drawable.ic_cloud_up, size = 20.dp, tint = cs.tertiary)
            Text(
                if (count == 1) "1 result is waiting to upload" else "$count results are waiting to upload",
                modifier = Modifier.weight(1f).padding(start = 12.dp), style = MaterialTheme.typography.bodyMedium, color = cs.tertiary,
            )
            TextButton(onClick = onView) { Text("View", color = cs.tertiary, style = MaterialTheme.typography.labelLarge) }
        }
    }
}

@Composable
private fun SectionRow(s: Section, enabled: Boolean, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceContainerLowest)
            .clickable(enabled = enabled, role = Role.Button, onClickLabel = "Take attendance for ${s.title}", onClick = onClick)
            .defaultMinSize(minHeight = 72.dp).padding(horizontal = 20.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(s.title, style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(s.id, style = MonoBody, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("${s.student_count} students", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Glyph(R.drawable.ic_chevron_right, size = 20.dp, tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

// ---- Uploads ----------------------------------------------------------------
@Composable
private fun UploadsTab(state: UiState, vm: AttendanceViewModel) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        ScreenHeader("Uploads", "Results waiting for the portal")
        if (state.pendingUploads == 0) {
            EmptyState(
                R.drawable.ic_cloud_up, "Nothing waiting",
                "Results upload as soon as the portal is reachable. You will see them here if it is not.",
            )
        } else {
            ListSurface {
                Row(
                    Modifier.fillMaxWidth().defaultMinSize(minHeight = 72.dp).padding(horizontal = 20.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            if (state.pendingUploads == 1) "1 result" else "${state.pendingUploads} results",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Text("Verified by the campus server", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    StatusChip("Waiting", ChipKind.Review)
                }
            }
            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                TonalButton("Retry now", onClick = vm::retryUploads, icon = R.drawable.ic_refresh, modifier = Modifier.fillMaxWidth())
                Text(
                    "The portal could not be reached. A result holds only who was present, never photos, and uploads automatically when you are back on the network.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

// ---- Device -----------------------------------------------------------------
@Composable
private fun DeviceTab(state: UiState, vm: AttendanceViewModel) {
    var editing by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        ScreenHeader("Device", state.teacherName)
        GroupHeader("Servers")
        ListSurface {
            SettingRow("Portal", state.portalUrl, onEdit = { editing = true }, editLabel = "Edit server addresses")
            Hairline()
            SettingRow("Campus server", state.mecUrl, onEdit = { editing = true }, editLabel = "Edit server addresses")
        }
        GroupHeader("This phone")
        ListSurface {
            Row(
                Modifier.fillMaxWidth().defaultMinSize(minHeight = 64.dp).padding(horizontal = 20.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(state.deviceLabel.ifBlank { "This phone" }, style = MaterialTheme.typography.titleSmall)
                    Text(
                        if (state.deviceRegistered) "Registered with the campus server" else "Not registered with this campus server yet",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (state.deviceRegistered) StatusChip("Active", ChipKind.Present) else StatusChip("Not registered", ChipKind.Review)
            }
        }
        GroupHeader("Privacy")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            PrivacyPoint(R.drawable.ic_camera, "Photos stay in memory and are discarded after processing.")
            PrivacyPoint(R.drawable.ic_lock, "Screenshots and backups of this app are blocked.")
            PrivacyPoint(R.drawable.ic_shield, "Requests are signed by a key that never leaves this phone's secure hardware.")
        }
        SecondaryButton(
            "Sign out", onClick = vm::logout, icon = R.drawable.ic_logout,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 24.dp),
        )
    }
    if (editing) {
        ServerDialog(state.portalUrl, state.mecUrl, onDismiss = { editing = false }) { p, m -> vm.saveServers(p, m); editing = false }
    }
}

@Composable
private fun SettingRow(label: String, value: String, onEdit: () -> Unit, editLabel: String) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 64.dp).padding(start = 20.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.secondary)
            Text(value, style = MonoBody)
        }
        IconButton(onClick = onEdit) {
            Glyph(R.drawable.ic_pencil, size = 20.dp, contentDescription = editLabel, tint = MaterialTheme.colorScheme.secondary)
        }
    }
}

@Composable
private fun PrivacyPoint(icon: Int, text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Glyph(icon, size = 20.dp, tint = MaterialTheme.colorScheme.primary)
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary)
    }
}

@Composable
private fun ServerDialog(portal: String, mec: String, onDismiss: () -> Unit, onSave: (String, String) -> Unit) {
    var p by remember { mutableStateOf(portal) }
    var m by remember { mutableStateOf(mec) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Server addresses", style = MaterialTheme.typography.titleLarge) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(p, { p = it }, label = { Text("Portal") }, singleLine = true, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth())
                OutlinedTextField(m, { m = it }, label = { Text("Campus server") }, singleLine = true, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth())
                Text(
                    "Phone and laptop must be on the same Wi-Fi network.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = { TextButton(onClick = { onSave(p, m) }, enabled = p.isNotBlank() && m.isNotBlank()) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
