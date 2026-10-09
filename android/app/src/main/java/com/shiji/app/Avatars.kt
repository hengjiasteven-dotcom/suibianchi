package com.shiji.app

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * 内置头像。
 *
 * 图片打进包里，服务端只在 profiles.avatar 存一个编号（avatar_1 ... avatar_7），
 * 这样换图片、加图片都只改客户端，不用动数据库。
 */
val AVATAR_IDS = listOf(
    "avatar_1",
    "avatar_2",
    "avatar_3",
    "avatar_4",
    "avatar_5",
    "avatar_6",
    "avatar_7",
)

fun avatarResId(id: String): Int? = when (id) {
    "avatar_1" -> R.drawable.avatar_1
    "avatar_2" -> R.drawable.avatar_2
    "avatar_3" -> R.drawable.avatar_3
    "avatar_4" -> R.drawable.avatar_4
    "avatar_5" -> R.drawable.avatar_5
    "avatar_6" -> R.drawable.avatar_6
    "avatar_7" -> R.drawable.avatar_7
    else -> null
}

private val AvatarBorder = Color(0x55FFFFFF)

/**
 * 圆形头像：选了内置头像就显示图片，没选过就用名字首字兜底。
 *
 * @param avatar 服务端存的头像编号，空串表示没设置
 * @param name   兜底用的名字
 */
@Composable
fun UserAvatar(
    avatar: String,
    name: String,
    size: Dp = 40.dp,
    onClick: (() -> Unit)? = null
) {
    val resId = avatarResId(avatar)
    Box(
        Modifier
            .size(size)
            .clip(CircleShape)
            .background(Color(0x40FFFFFF))
            .border(1.dp, AvatarBorder, CircleShape)
            .then(if (onClick != null) Modifier.clickable { onClick() } else Modifier),
        contentAlignment = Alignment.Center
    ) {
        if (resId != null) {
            Image(
                painter = painterResource(resId),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(size).clip(CircleShape)
            )
        } else {
            Text(
                name.trim().takeIf { it.isNotEmpty() }?.take(1) ?: "吃",
                fontSize = (size.value * 0.4f).sp,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

/** 头像选择用的圆形缩略图，选中的加一圈米黄色描边。 */
@Composable
fun AvatarChoice(
    avatar: String,
    selected: Boolean,
    size: Dp = 58.dp,
    onClick: () -> Unit
) {
    val resId = avatarResId(avatar)
    Box(
        Modifier
            .size(size)
            .clip(CircleShape)
            .background(Color(0x40FFFFFF))
            .border(
                width = if (selected) 3.dp else 1.dp,
                color = if (selected) Color(0xFFE8D9B0) else AvatarBorder,
                shape = CircleShape
            )
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        if (resId != null) {
            Image(
                painter = painterResource(resId),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(size).clip(CircleShape)
            )
        }
    }
}
