package com.shiji.app

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.layout.ContentScale
import coil.compose.AsyncImage
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shiji.app.data.CategoryShare
import com.shiji.app.data.FeedPost
import com.shiji.app.data.FriendCard
import com.shiji.app.data.FriendRequestItem
import com.shiji.app.data.SharePayload

/** 广场里的三个位置：列表 / 朋友圈 / 和某个好友的分享窗口。 */
sealed interface SquareRoute {
    data object Home : SquareRoute
    data object Moments : SquareRoute
    data class Chat(val friend: FriendCard) : SquareRoute
}

private val PanelFill = Color(0x2EFFFFFF)
private val PanelBorder = Color(0x40FFFFFF)

private fun Modifier.glassPanel(radius: Dp = 16.dp): Modifier = this
    .clip(RoundedCornerShape(radius))
    .background(PanelFill)
    .border(1.dp, PanelBorder, RoundedCornerShape(radius))

private fun slotLabel(slot: String): String = when (slot) {
    "breakfast" -> "早餐"
    "lunch" -> "午餐"
    "dinner" -> "晚餐"
    "supper" -> "夜宵"
    else -> "一餐"
}

/** 把 ISO 时间压成 "10-09 12:30"，广场里够用了。 */
private fun shortTime(iso: String): String {
    val date = iso.take(10)
    val time = iso.drop(11).take(5)
    return if (date.length == 10 && time.length == 5) "${date.substring(5)} $time" else iso.take(16)
}

private fun displayName(card: FriendCard?): String {
    val name = card?.name.orEmpty().trim()
    return name.ifEmpty { "用户${card?.user_id ?: "?"}" }
}


/** 一条分享的内容：最近一餐就列吃了什么，周报就画类别占比。 */
@Composable
fun ShareCardBody(post: FeedPost) {
    val payload = post.payload
    Column(Modifier.fillMaxWidth()) {
        if (payload.type == "weekly") {
            Text(
                payload.title ?: "最近 7 天食物类别占比",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.outline
            )
            Spacer(Modifier.height(8.dp))
            CategoryBars(payload.category_share)
        } else {
            val meals = payload.meals
            if (meals.isEmpty()) {
                Text("这一餐没有记录", fontSize = 13.sp, color = MaterialTheme.colorScheme.outline)
            } else {
                meals.forEach { meal ->
                    Row(Modifier.padding(vertical = 3.dp)) {
                        Text(
                            slotLabel(meal.meal_slot),
                            fontSize = 12.sp,
                            color = Color(0xFFE8D9B0),
                            modifier = Modifier.width(40.dp)
                        )
                        Column {
                            // 餐名放第一行：一餐的主语是吃了什么菜，不是食材清单
                            val dishText = meal.dishes.joinToString("、")
                            Text(
                                dishText.ifEmpty {
                                    meal.foods.firstOrNull() ?: "（没写具体内容）"
                                },
                                fontSize = 14.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = Color(0xE6FFFFFF)
                            )
                            // 食材作为补充；没餐名时首项已经在上面显示过了
                            val rest = if (dishText.isEmpty()) meal.foods.drop(1) else meal.foods
                            if (rest.isNotEmpty()) {
                                Spacer(Modifier.height(2.dp))
                                Text(
                                    rest.joinToString("、"),
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.outline
                                )
                            }
                            // 分享里带的照片（服务端现签的地址）
                            if (meal.photos.isNotEmpty()) {
                                Spacer(Modifier.height(6.dp))
                                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    items(meal.photos) { photo ->
                                        AsyncImage(
                                            model = photo.url,
                                            contentDescription = null,
                                            contentScale = ContentScale.Crop,
                                            modifier = Modifier
                                                .size(96.dp)
                                                .clip(RoundedCornerShape(8.dp))
                                                .background(Color(0x26FFFFFF))
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/** 横向占比条，比环形图更适合塞在广场的小卡片里。 */
@Composable
private fun CategoryBars(shares: List<CategoryShare>) {
    if (shares.isEmpty()) {
        Text("这周还没有记录", fontSize = 13.sp, color = MaterialTheme.colorScheme.outline)
        return
    }
    Column {
        shares.take(6).forEach { item ->
            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(item.category, fontSize = 12.sp, modifier = Modifier.width(96.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
                Box(
                    Modifier
                        .weight(1f)
                        .height(8.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(Color(0x26FFFFFF))
                ) {
                    Box(
                        Modifier
                            .fillMaxWidth((item.percent / 100.0).toFloat().coerceIn(0.02f, 1f))
                            .height(8.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(Color(0xB3E8D9B0))
                    )
                }
                Text(
                    "${item.percent}%",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.width(48.dp),
                    maxLines = 1
                )
            }
        }
    }
}

// ------------------------------------------------------------------ 广场首页

/** 广场首页：最上面是朋友圈入口，下面是好友列表。 */
@Composable
fun SquareHomeScreen(
    friends: List<FriendCard>,
    requests: List<FriendRequestItem>,
    busy: Boolean,
    onOpenMoments: () -> Unit,
    onOpenChat: (FriendCard) -> Unit,
    onAddFriend: (String) -> Unit,
    onAcceptRequest: (Int) -> Unit,
    onRejectRequest: (Int) -> Unit
) {
    var showAdd by remember { mutableStateOf(false) }
    var newId by remember { mutableStateOf("") }

    if (showAdd) {
        AlertDialog(
            onDismissRequest = { showAdd = false },
            modifier = Modifier.border(1.dp, PanelBorder, RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(20.dp),
            containerColor = com.shiji.app.data.DialogGlass,
            title = { Text("加好友") },
            text = {
                Column {
                    Text(
                        "输入对方的 6 位用户码（字母和数字）。你自己的码在个人主页。",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.outline
                    )
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(
                        value = newId,
                        onValueChange = { input ->
                            // 只留字母和数字，统一小写，最多 6 位
                            newId = input.filter { it.isLetterOrDigit() }.lowercase().take(6)
                        },
                        label = { Text("用户码") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (newId.length == 6) {
                            onAddFriend(newId)
                            newId = ""
                            showAdd = false
                        }
                    },
                    enabled = newId.length == 6
                ) { Text("添加") }
            },
            dismissButton = { TextButton(onClick = { showAdd = false }) { Text("取消") } }
        )
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        // 朋友圈入口
        Row(
            Modifier
                .fillMaxWidth()
                .glassPanel()
                .clickable { onOpenMoments() }
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(Color(0x40FFFFFF)),
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Filled.Groups, contentDescription = null, modifier = Modifier.size(22.dp))
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("朋友圈", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Text("所有人分享的餐食都在这里", fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            }
            if (busy) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
        }

        Spacer(Modifier.height(16.dp))

        // 谁申请加我：一行提醒，就地接受或拒绝
        if (requests.isNotEmpty()) {
            Text("好友申请", fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            requests.forEach { req ->
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .glassPanel(14.dp)
                        .padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    UserAvatar(req.from.avatar, displayName(req.from), 36.dp)
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(displayName(req.from), fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text(
                            "申请加你为好友 · ID ${req.from.code}",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.outline,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    TextButton(onClick = { onRejectRequest(req.request_id) }) {
                        Text("拒绝", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                    }
                    TextButton(onClick = { onAcceptRequest(req.request_id) }) {
                        Text("接受", fontSize = 12.sp)
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("好友", fontSize = 14.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
            TextButton(onClick = { showAdd = true }) {
                Icon(Icons.Filled.PersonAdd, contentDescription = null, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(4.dp))
                Text("加好友", fontSize = 13.sp)
            }
        }
        Spacer(Modifier.height(4.dp))

        if (friends.isEmpty()) {
            Text(
                "还没有好友。点右上「加好友」，填对方的 6 位用户码就行。",
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.padding(vertical = 12.dp)
            )
        } else {
            LazyColumn(Modifier.weight(1f)) {
                items(friends, key = { it.user_id }) { friend ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .glassPanel(14.dp)
                            .clickable { onOpenChat(friend) }
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        UserAvatar(friend.avatar, displayName(friend), 38.dp)
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(displayName(friend), fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                            Text(
                                friend.signature.ifBlank { "ID ${friend.code}" },
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.outline,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                        Text("›", fontSize = 18.sp, color = MaterialTheme.colorScheme.outline)
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------ 朋友圈

/** 朋友圈：全屏盖住 TAB，所有人发的内容都在这里。 */
@Composable
fun MomentsScreen(
    posts: List<FeedPost>,
    busy: Boolean,
    onAvatarClick: (FriendCard) -> Unit,
    onShare: (String) -> Unit
) {
    Column(Modifier.fillMaxSize().padding(16.dp)) {

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(onClick = { onShare("latest") }, modifier = Modifier.weight(1f)) {
                Text("分享最近一餐", fontSize = 13.sp, maxLines = 1)
            }
            Button(onClick = { onShare("weekly") }, modifier = Modifier.weight(1f)) {
                Text("分享本周报告", fontSize = 13.sp, maxLines = 1)
            }
        }
        if (busy) {
            Spacer(Modifier.height(8.dp))
            CircularProgressIndicator(Modifier.align(Alignment.End).size(16.dp), strokeWidth = 2.dp)
        }

        Spacer(Modifier.height(12.dp))

        if (posts.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("还没有人分享，你可以做第一个。", fontSize = 13.sp, color = MaterialTheme.colorScheme.outline)
            }
        } else {
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(posts, key = { it.post_id }) { post -> FeedPostCard(post, onAvatarClick) }
            }
        }
    }
}

/** 朋友圈里的一条：头像可点，点了能看到对方的 ID。 */
@Composable
private fun FeedPostCard(post: FeedPost, onAvatarClick: (FriendCard) -> Unit) {
    Row(Modifier.fillMaxWidth().glassPanel().padding(12.dp)) {
        UserAvatar(post.author.avatar, displayName(post.author), 40.dp) { onAvatarClick(post.author) }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(displayName(post.author), fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                if (post.mine) {
                    Spacer(Modifier.width(6.dp))
                    Text("我", fontSize = 10.sp, color = Color(0xFFE8D9B0))
                }
                Spacer(Modifier.weight(1f))
                Text(shortTime(post.created_at), fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            }
            Spacer(Modifier.height(8.dp))
            ShareCardBody(post)
        }
    }
}

// ------------------------------------------------------------------ 好友分享窗口

/**
 * 和某个好友的分享窗口。
 *
 * 这里只能发食物内容，不能发文字；底部两个按钮固定在 TAB 栏之上。
 */
@Composable
fun FriendChatScreen(
    friend: FriendCard,
    posts: List<FeedPost>,
    busy: Boolean,
    onBack: () -> Unit,
    onShare: (String) -> Unit
) {
    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回", modifier = Modifier.size(22.dp))
            }
            Text(displayName(friend), fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.width(8.dp))
            // 显示 6 位对外码；对方改名后这里会跟着变
            Text("ID ${friend.code}", fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            Spacer(Modifier.weight(1f))
            if (busy) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
        }

        if (posts.isEmpty()) {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text(
                    "还没有互相分享过。\n下面可以把今天吃的或这周占比发过去。",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.outline
                )
            }
        } else {
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(posts, key = { it.post_id }) { post -> ChatBubble(post) }
            }
        }

        // 固定在 TAB 栏之上：左边分享今天吃的，右边分享一周占比
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Button(onClick = { onShare("latest") }, modifier = Modifier.weight(1f)) {
                Text("分享今天吃的", fontSize = 13.sp, maxLines = 1)
            }
            Button(onClick = { onShare("weekly") }, modifier = Modifier.weight(1f)) {
                Text("分享一周占比", fontSize = 13.sp, maxLines = 1)
            }
        }
    }
}

/** 私聊里的一条：自己发的靠右，对方发的靠左。 */
@Composable
private fun ChatBubble(post: FeedPost) {
    val align = if (post.mine) Alignment.CenterEnd else Alignment.CenterStart
    Box(Modifier.fillMaxWidth(), contentAlignment = align) {
        Column(
            Modifier
                .fillMaxWidth(0.82f)
                .glassPanel()
                .padding(10.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                UserAvatar(post.author.avatar, displayName(post.author), 22.dp)
                Spacer(Modifier.width(6.dp))
                Text(displayName(post.author), fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
                Spacer(Modifier.weight(1f))
                Text(shortTime(post.created_at), fontSize = 10.sp, color = MaterialTheme.colorScheme.outline)
            }
            Spacer(Modifier.height(6.dp))
            ShareCardBody(post)
        }
    }
}

// ------------------------------------------------------------------ 名片

/** 公开名片弹窗：只显示昵称/ID/城市/性别，外加加好友。 */
@Composable
fun UserCardDialog(
    card: FriendCard,
    onAddFriend: (String) -> Unit,
    onDismiss: () -> Unit
) {
    val clipboard = LocalClipboardManager.current
    var copied by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.border(1.dp, PanelBorder, RoundedCornerShape(20.dp)),
        shape = RoundedCornerShape(20.dp),
        containerColor = com.shiji.app.data.DialogGlass,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                UserAvatar(card.avatar, displayName(card), 42.dp)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(displayName(card), fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "ID：${card.code}",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.outline
                        )
                        Spacer(Modifier.width(2.dp))
                        // ID 旁边的小复制键：方便直接发给别人
                        IconButton(
                            onClick = {
                                clipboard.setText(AnnotatedString(card.code))
                                copied = true
                            },
                            modifier = Modifier.size(22.dp)
                        ) {
                            Icon(
                                Icons.Filled.ContentCopy,
                                contentDescription = "复制 ID",
                                modifier = Modifier.size(13.dp),
                                tint = if (copied) Color(0xFFE8D9B0) else MaterialTheme.colorScheme.outline
                            )
                        }
                        if (copied) {
                            Text("已复制", fontSize = 10.sp, color = Color(0xFFE8D9B0))
                        }
                    }
                }
            }
        },
        text = {
            Column(Modifier.heightIn(max = 220.dp)) {
                if (card.signature.isNotBlank()) {
                    Text(card.signature, fontSize = 13.sp)
                    Spacer(Modifier.height(6.dp))
                }
                Text(
                    listOfNotNull(
                        card.city.takeIf { it.isNotBlank() },
                        when (card.gender) {
                            "male" -> "男"
                            "female" -> "女"
                            "secret" -> "保密"
                            else -> null
                        }
                    ).joinToString(" · ").ifBlank { "没有更多公开信息" },
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.outline
                )
            }
        },
        confirmButton = {
            when {
                card.is_me || card.is_friend ->
                    TextButton(onClick = onDismiss) { Text("关闭") }
                // 自己已经申请过：只提示，不重复发
                card.friend_status == "pending_out" ->
                    TextButton(onClick = onDismiss) { Text("等待对方同意") }
                card.friend_status == "pending_in" ->
                    TextButton(onClick = { onAddFriend(card.code) }) { Text("同意加好友") }
                else ->
                    TextButton(onClick = { onAddFriend(card.code) }) { Text("加好友") }
            }
        },
        dismissButton = {
            if (!card.is_me && !card.is_friend && card.friend_status != "pending_out") {
                TextButton(onClick = onDismiss) { Text("关闭") }
            }
        }
    )
}
