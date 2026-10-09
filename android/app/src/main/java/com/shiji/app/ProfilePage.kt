package com.shiji.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.shiji.app.data.AlertDialogHost
import com.shiji.app.data.ChoiceItem
import com.shiji.app.data.CheckItem
import com.shiji.app.data.Profile

/**
 * 个人主页：头像 / 名字 / 用户 ID / 个性签名 + 设置 + 权限。
 * 从右上角头像进入，不占底部 TAB。
 */
@Composable
fun ProfilePage(
    profile: Profile?,
    busy: Boolean,
    message: String,
    onSaveProfile: (String, String, String, String) -> Unit,
    // 选内置头像：立即保存，不用进编辑弹窗
    onPickAvatar: (String) -> Unit,
    // 改 6 位对外 ID
    onChangeCode: (String) -> Unit,
    onLogout: () -> Unit,
    onDeleteAccount: () -> Unit,
    onOpenPrivacy: () -> Unit
) {
    var editing by remember { mutableStateOf(false) }
    // 点头像弹出来的选择框
    var pickingAvatar by remember { mutableStateOf(false) }
    // 改 ID 的弹窗
    var editingCode by remember { mutableStateOf(false) }
    var newCode by remember { mutableStateOf("") }
    var confirmingDelete by remember { mutableStateOf(false) }

    if (pickingAvatar) {
        AlertDialog(
            onDismissRequest = { pickingAvatar = false },
            modifier = Modifier.border(1.dp, Color(0x40FFFFFF), RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(20.dp),
            containerColor = com.shiji.app.data.DialogGlass,
            title = { Text("选头像") },
            text = {
                Column {
                    Text(
                        "选一个，好友和朋友圈里都会显示它。",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.outline
                    )
                    Spacer(Modifier.height(14.dp))
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        AVATAR_IDS.forEach { id ->
                            AvatarChoice(
                                avatar = id,
                                selected = profile?.avatar == id,
                                size = 40.dp
                            ) {
                                onPickAvatar(id)
                                pickingAvatar = false
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { pickingAvatar = false }) { Text("关闭") }
            }
        )
    }

    if (editingCode) {
        AlertDialog(
            onDismissRequest = { editingCode = false },
            modifier = Modifier.border(1.dp, Color(0x40FFFFFF), RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(20.dp),
            containerColor = com.shiji.app.data.DialogGlass,
            title = { Text("改 ID") },
            text = {
                Column {
                    Text(
                        "6 位，只能用数字和小写字母。注意：只能改这一次，改完就锁死，旧 ID 立刻失效。",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.outline
                    )
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(
                        value = newCode,
                        onValueChange = { input ->
                            // 只留字母和数字，统一小写，最多 6 位
                            newCode = input.filter { it.isLetterOrDigit() }.lowercase().take(6)
                        },
                        label = { Text("新的 ID") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        onChangeCode(newCode)
                        editingCode = false
                    },
                    enabled = newCode.length == 6 && newCode != profile?.code
                ) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = { editingCode = false }) { Text("取消") }
            }
        )
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp, vertical = 8.dp)
    ) {
        // 名片
        Column(
            Modifier
                .fillMaxWidth()
                .glassPanel()
                .padding(16.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // 点头像本身就是换头像的入口
                UserAvatar(
                    avatar = profile?.avatar.orEmpty(),
                    name = profile?.name.orEmpty(),
                    size = 62.dp
                ) { pickingAvatar = true }
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        profile?.name?.takeIf { it.isNotBlank() } ?: "还没有名字",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.height(2.dp))
                    // 对外只露这个 6 位码：别人加好友、朋友圈名片用的都是它
                    // 对外只露这个 6 位码：别人加好友、朋友圈名片用的都是它
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "ID：${profile?.code?.ifBlank { null } ?: "-"}",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.outline
                        )
                        Spacer(Modifier.width(2.dp))
                        if (profile?.code_changeable != false) {
                            IconButton(
                                onClick = {
                                    newCode = profile?.code.orEmpty()
                                    editingCode = true
                                },
                                modifier = Modifier.size(22.dp)
                            ) {
                                Icon(
                                    Icons.Filled.Edit,
                                    contentDescription = "改 ID",
                                    modifier = Modifier.size(13.dp),
                                    tint = MaterialTheme.colorScheme.outline
                                )
                            }
                        } else {
                            // 已经改过一次，锁死了
                            Icon(
                                Icons.Filled.Lock,
                                contentDescription = "ID 已锁定",
                                modifier = Modifier.size(12.dp),
                                tint = MaterialTheme.colorScheme.outline
                            )
                        }
                    }
                    val phoneText = profile?.phone.orEmpty()
                    if (phoneText.isNotBlank()) {
                        Text(phoneText, fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                    }
                }
                TextButton(onClick = { editing = true }, enabled = !busy) { Text("编辑", fontSize = 13.sp) }
            }
            Spacer(Modifier.height(10.dp))
            Text(
                profile?.signature?.takeIf { it.isNotBlank() } ?: "写一句个性签名吧",
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }


        Spacer(Modifier.height(14.dp))
        SectionTitle("资料")
        InfoRow("城市", profile?.city?.takeIf { it.isNotBlank() } ?: "未设置")
        InfoRow("性别", genderLabel(profile?.gender))

        Spacer(Modifier.height(16.dp))
        SectionTitle("权限")
        // 拍照、选图走的是系统相机 / 相册，不需要 App 自己拿权限
        PermissionRow("相机", "可用（调系统相机）", ok = true, showSettings = false)
        PermissionRow("相册", "可用（调系统相册）", ok = true, showSettings = false)
        val locationOk = isGranted(LocalContext.current, Manifest.permission.ACCESS_FINE_LOCATION)
        PermissionRow("定位", if (locationOk) "已允许" else "未开启", ok = locationOk)
        val notifyOk = isGranted(LocalContext.current, notificationPermission())
        PermissionRow("通知", if (notifyOk) "已允许" else "未开启", ok = notifyOk)

        Spacer(Modifier.height(16.dp))
        SectionTitle("账号")
        OutlinedButton(onClick = onLogout, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
            Text("退出登录", fontSize = 13.sp)
        }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(
            onClick = { confirmingDelete = true },
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error)
        ) {
            Text("注销账号", fontSize = 13.sp, color = MaterialTheme.colorScheme.error)
        }
        Text(
            "注销会删除你的全部记录、档案、忌口爱好和设备登录信息，无法恢复。",
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.padding(top = 6.dp)
        )

        Spacer(Modifier.height(16.dp))
        SectionTitle("设置")
        Row(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .clickable { onOpenPrivacy() }
                .padding(vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("隐私政策", fontSize = 13.sp, modifier = Modifier.weight(1f))
            Text("›", fontSize = 16.sp, color = MaterialTheme.colorScheme.outline)
        }

        if (message.isNotBlank()) {
            Spacer(Modifier.height(12.dp))
            Text(message, color = MaterialTheme.colorScheme.primary, fontSize = 13.sp)
        }
        // 右下角版本号
        Spacer(Modifier.height(18.dp))
        Text(
            "v" + BuildConfig.VERSION_NAME,
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.align(Alignment.End)
        )
        Spacer(Modifier.height(24.dp))
    }

    if (editing) {
        EditProfileDialog(
            profile = profile,
            onDismiss = { editing = false },
            onSave = { name, signature, city, gender ->
                editing = false
                onSaveProfile(name, signature, city, gender)
            }
        )
    }

    if (confirmingDelete) {
        AlertDialogHost(
            title = "确认注销账号？",
            body = "注销后你的每一餐记录、档案、忌口与爱好、设备登录信息都会被删除，且无法恢复。日常记录只能编辑不能删除，这一步是唯一的清空方式。",
            confirmText = "确认注销",
            dismissText = "再想想",
            onConfirm = {
                confirmingDelete = false
                onDeleteAccount()
            },
            onDismiss = { confirmingDelete = false }
        )
    }
}



/** 毛玻璃面板：半透明底 + 细边。 */
private fun Modifier.glassPanel(radius: androidx.compose.ui.unit.Dp = 18.dp): Modifier = this
    .clip(RoundedCornerShape(radius))
    .background(Color(0x2EFFFFFF))
    .border(1.dp, Color(0x40FFFFFF), RoundedCornerShape(radius))

@Composable
private fun SectionTitle(text: String) {
    Text(text, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(bottom = 6.dp))
}


/** 只读一行：标签 + 值。 */
@Composable
private fun InfoRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, fontSize = 13.sp, modifier = Modifier.width(72.dp))
        Text(value, fontSize = 13.sp, color = MaterialTheme.colorScheme.outline)
    }
}


private fun genderLabel(value: String?): String = when (value) {
    "male" -> "男"
    "female" -> "女"
    "secret" -> "保密"
    else -> "未设置"
}


@Composable
private fun EditProfileDialog(
    profile: Profile?,
    onDismiss: () -> Unit,
    onSave: (String, String, String, String) -> Unit
) {
    var name by remember { mutableStateOf(profile?.name.orEmpty()) }
    var signature by remember { mutableStateOf(profile?.signature.orEmpty()) }
    var city by remember { mutableStateOf(profile?.city.orEmpty()) }
    var gender by remember { mutableStateOf(profile?.gender.orEmpty()) }
    AlertDialogHost(
        title = "编辑资料",
        body = "名字和个性签名会显示在个人主页",
        confirmText = "保存",
        dismissText = "取消",
        onConfirm = { onSave(name.trim(), signature.trim(), city.trim(), gender) },
        onDismiss = onDismiss,
        content = {
            Column(Modifier.heightIn(max = 400.dp).verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("名字") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = signature,
                    onValueChange = { signature = it },
                    label = { Text("个性签名") },
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = city,
                    onValueChange = { city = it },
                    label = { Text("城市") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                Text("性别", fontSize = 13.sp)
                Row(Modifier.fillMaxWidth()) {
                    ChoiceItem("男", gender == "male", { gender = "male" }, Modifier.weight(1f))
                    ChoiceItem("女", gender == "female", { gender = "female" }, Modifier.weight(1f))
                    ChoiceItem("保密", gender == "secret", { gender = "secret" }, Modifier.weight(1f))
                }
            }
        }
    )
}

/** 一行权限状态；需要时可以去系统设置里改。 */
@Composable
private fun PermissionRow(
    label: String,
    status: String,
    ok: Boolean,
    showSettings: Boolean = true
) {
    val context = LocalContext.current
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, fontSize = 13.sp, modifier = Modifier.width(72.dp))
        Text(
            status,
            fontSize = 12.sp,
            color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline,
            modifier = Modifier.weight(1f)
        )
        if (showSettings) {
            OutlinedButton(onClick = { openAppSettings(context) }) { Text("去设置", fontSize = 12.sp) }
        }
    }
}

private fun isGranted(context: android.content.Context, permission: String): Boolean =
    ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

private fun notificationPermission(): String =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) Manifest.permission.POST_NOTIFICATIONS
    else Manifest.permission.ACCESS_NETWORK_STATE

private fun openAppSettings(context: android.content.Context) {
    val intent = Intent(
        Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
        Uri.fromParts("package", context.packageName, null)
    )
    context.startActivity(intent)
}
