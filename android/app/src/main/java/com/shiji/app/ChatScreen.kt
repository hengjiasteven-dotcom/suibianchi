package com.shiji.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import com.shiji.app.data.PendingFacts
import com.shiji.app.data.Preference
import com.shiji.app.data.Restriction
import com.shiji.app.data.LevelPicker
import com.shiji.app.data.PREFERENCE_LEVELS
import com.shiji.app.data.RESTRICTION_LEVELS
import com.shiji.app.data.preferenceDotColor
import com.shiji.app.data.preferenceLevel
import com.shiji.app.data.preferenceLevelText
import com.shiji.app.data.restrictionDotColor
import com.shiji.app.data.restrictionLevel
import com.shiji.app.data.restrictionLevelText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shiji.app.data.ApiClient
import com.shiji.app.data.ChatMessageRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.derivedStateOf
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * 对话状态放在 Composable 外面：切 TAB 不会清空，
 * 只有退出软件超过 10 分钟，服务端才会结束并清空这次对话。
 */
object ChatStore {
    var sessionId by mutableStateOf<String?>(null)
    var notice by mutableStateOf("")
    var hint by mutableStateOf("")
    var sending by mutableStateOf(false)
    var pending by mutableStateOf<PendingFacts?>(null)
    val messages = mutableStateListOf<Pair<Boolean, String>>()
    val likes = mutableStateListOf<String>()
}

/**
 * 推荐页 = 聊天窗口：用户直接问「吃什么」，AI 结合最近的食材记录和本次对话聊到的口味来答。
 * 会话状态在 ChatStore 里，切 TAB 不会丢；退出软件超过 10 分钟由服务端结束并清空。
 */
@Composable
fun ChatScreen() {
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }
    if (ChatStore.messages.isEmpty()) {
        ChatStore.messages.add(
            false to "我是你的吃饭参谋。说说你现在想吃什么、或者有什么不想吃的，我帮你拿主意。"
        )
    }

    suspend fun refreshPending() {
        runCatching { ChatStore.pending = ApiClient.api.pendingFacts() }
    }
    fun decideRestriction(item: Restriction, level: Int, accept: Boolean) {
        scope.launch {
            runCatching {
                ApiClient.api.confirmRestriction(item.id, confirmed = accept, level = level)
            }
            ChatStore.hint = if (accept) {
                "已记下忌口：${item.keyword} · ${restrictionLevelText(level)}"
            } else {
                "已忽略：${item.keyword}"
            }
            refreshPending()
        }
    }

    fun decidePreference(item: Preference, level: Int, accept: Boolean) {
        scope.launch {
            runCatching {
                // 爱好也用 1~3 档，服务端存在 weight 字段里
                ApiClient.api.confirmPreference(item.id, confirmed = accept, weight = level.toDouble())
            }
            ChatStore.hint = if (accept) {
                "已记下爱好：${item.keyword} · ${preferenceLevelText(level.toDouble())}"
            } else {
                "已忽略：${item.keyword}"
            }
            refreshPending()
        }
    }

    // 只在第一次进推荐页时开会话；切 TAB 回来继续用同一个，退出软件 10 分钟后服务端自动清
    LaunchedEffect(Unit) {
        if (ChatStore.sessionId == null) {
            try {
                val session = ApiClient.api.chatStart()
                ChatStore.sessionId = session.session_id
                ChatStore.notice = session.notice
            } catch (e: Exception) {
                ChatStore.hint = "对话开不起来：${e.message ?: "网络异常"}"
            }
        }
        // 每次回到推荐页都对一遍待确认列表，数据变了就不会留旧条目
        refreshPending()
    }

    LaunchedEffect(ChatStore.messages.size) {
        if (ChatStore.messages.isNotEmpty()) {
            // 等新消息完成布局再滚，否则会停在倒数第二条
            delay(80)
            listState.animateScrollToItem(ChatStore.messages.lastIndex)
        }
    }

    fun send() {
        val text = input.trim()
        val sid = ChatStore.sessionId
        if (text.isEmpty() || ChatStore.sending || sid == null) {
            return
        }
        input = ""
        ChatStore.messages.add(true to text)
        ChatStore.sending = true
        scope.launch {
            try {
                val reply = ApiClient.api.chatMessage(sid, ChatMessageRequest(text))
                ChatStore.messages.add(false to reply.reply)
                ChatStore.likes.clear()
                ChatStore.likes.addAll(reply.likes)
                if (reply.extracted.isNotEmpty()) {
                    ChatStore.hint = "记下了 ${reply.extracted.size} 条，在下面选好程度再确认"
                    refreshPending()
                } else {
                    ChatStore.hint = ""
                }
            } catch (e: Exception) {
                ChatStore.hint = "发送失败：${e.message ?: "网络异常"}"
            } finally {
                ChatStore.sending = false
            }
        }
    }

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        if (ChatStore.notice.isNotBlank()) {
            Text(
                ChatStore.notice,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.padding(top = 4.dp, bottom = 6.dp)
            )
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
            ) {
                itemsIndexed(ChatStore.messages) { _, message ->
                    ChatBubble(mine = message.first, text = message.second)
                }
            }
            // 滑上去看历史时，给个一键回到最新的箭头
            // 还有没滑到底（还能向下滑）就显示箭头
            val atBottom by remember { derivedStateOf { !listState.canScrollForward } }
            if (!atBottom) {
                IconButton(
                    onClick = {
                        scope.launch { listState.animateScrollToItem(ChatStore.messages.lastIndex) }
                    },
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(10.dp)
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(Color(0x73FFFFFF))
                ) {
                    Icon(
                        Icons.Filled.ArrowDownward,
                        contentDescription = "回到最新",
                        tint = Color(0xFF2A2114),
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
        }
        if (ChatStore.hint.isNotBlank()) {
            Text(
                ChatStore.hint,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 4.dp)
            )
        }
        // 对话里新学到的爱好/忌口，就在这里逐条确认，确认后才进档案
        // 忌口和爱好都能同时好几条待确认，同一样东西只会出现一条。
        val pendingRestrictions = ChatStore.pending?.restrictions.orEmpty()
        val pendingPreferences = ChatStore.pending?.preferences.orEmpty()
        if (pendingRestrictions.isNotEmpty() || pendingPreferences.isNotEmpty()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .padding(bottom = 6.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color(0x47101418))
                    .heightIn(max = 230.dp)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 8.dp, vertical = 6.dp)
            ) {
                Text(
                    "聊到这些了，先选个程度再确认",
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(bottom = 2.dp)
                )
                pendingRestrictions.forEach { item ->
                    PendingRestrictionRow(
                        item = item,
                        onConfirm = { level -> decideRestriction(item, level, true) },
                        onReject = { decideRestriction(item, restrictionLevel(item.level), false) }
                    )
                }
                pendingPreferences.forEach { item ->
                    PendingPreferenceRow(
                        item = item,
                        onConfirm = { level -> decidePreference(item, level, true) },
                        onReject = { decidePreference(item, preferenceLevel(item.weight), false) }
                    )
                }
            }
        }
        Row(
            Modifier.fillMaxWidth().padding(bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                placeholder = { Text("想吃什么？", fontSize = 13.sp) },
                maxLines = 3,
                modifier = Modifier.weight(1f)
            )
            Spacer(Modifier.width(8.dp))
            Button(
                onClick = { send() },
                enabled = !ChatStore.sending && ChatStore.sessionId != null,
                modifier = Modifier.padding(bottom = 4.dp)
            ) { Text("发送", fontSize = 14.sp) }
        }
    }
}

/** 左：AI；右：自己。 */
@Composable
private fun ChatBubble(mine: Boolean, text: String) {
    val shape = RoundedCornerShape(14.dp)
    Box(
        Modifier.fillMaxWidth(),
        contentAlignment = if (mine) Alignment.CenterEnd else Alignment.CenterStart
    ) {
        Text(
            text,
            fontSize = 14.sp,
            color = if (mine) Color(0xFF2A2114) else Color.White,
            modifier = Modifier
                .fillMaxWidth(0.86f)
                .clip(shape)
                .background(if (mine) Color(0x8CE8D9B0) else Color(0x40101418))
                .padding(horizontal = 12.dp, vertical = 10.dp)
        )
    }
}


/** 待确认的爱好：程度也分三档，选好再确认。 */
@Composable
private fun PendingPreferenceRow(
    item: Preference,
    onConfirm: (Int) -> Unit,
    onReject: () -> Unit
) {
    var level by remember(item.id) { mutableStateOf(preferenceLevel(item.weight)) }
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "爱好",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.width(34.dp)
            )
            Text(item.keyword, fontSize = 13.sp, modifier = Modifier.weight(1f))
            TextButton(onClick = onReject) { Text("拒绝", fontSize = 11.sp) }
            TextButton(onClick = { onConfirm(level) }) { Text("确定", fontSize = 11.sp) }
        }
        LevelPicker(
            options = PREFERENCE_LEVELS,
            selected = level,
            onSelect = { level = it },
            dotColor = ::preferenceDotColor,
            // 档位往左靠：三档要排在一行里
            modifier = Modifier.padding(start = 12.dp)
        )
    }
}


/** 待确认的忌口：程度分三档，选好再确认。 */
@Composable
private fun PendingRestrictionRow(
    item: Restriction,
    onConfirm: (Int) -> Unit,
    onReject: () -> Unit
) {
    var level by remember(item.id) { mutableStateOf(restrictionLevel(item.level)) }
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "忌口",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.width(34.dp)
            )
            Text(item.keyword, fontSize = 13.sp, modifier = Modifier.weight(1f))
            TextButton(onClick = onReject) { Text("拒绝", fontSize = 11.sp) }
            TextButton(onClick = { onConfirm(level) }) { Text("确定", fontSize = 11.sp) }
        }
        LevelPicker(
            options = RESTRICTION_LEVELS,
            selected = level,
            onSelect = { level = it },
            dotColor = ::restrictionDotColor,
            modifier = Modifier.padding(start = 12.dp)
        )
    }
}
