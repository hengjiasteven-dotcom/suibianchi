package com.shiji.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val GUIDE_SECTIONS = listOf(
    "1. 记录一餐" to
        "点“发布这一餐”，可以拍照、从相册选多张，或者只写文字。识别出来的是菜品和食材，确认后才会保存；热量由后台估算，晚一点回到记录里刷新就能看到。",
    "2. 日志" to
        "日志按周和月查看，一天固定四餐：早餐、午餐、晚餐、夜宵。每一餐只保留一条记录，点某一天或某一餐可以修改；再记同一餐会提示合并或覆盖。",
    "3. 报告" to
        "报告按最近 7 天统计食材类别占比、最常吃的食材和缺口提醒。它只做饮食结构参考，不替代医疗建议。",
    "4. 推荐" to
        "推荐是一个聊天窗口，直接问“我吃什么”就行。聊到你喜欢或不能接受的食物时，会弹出确认卡片；确认后会记进你的个人档案，并在以后推荐时避开或优先考虑。",
    "5. 广场" to
        "广场可以发布今天吃的或最近一周的食物类型占比，也可以通过 6 位 ID 加好友。好友只能互相分享食物内容，不会展示你的其他隐私信息。",
    "6. 数据与隐私" to
        "头像、城市、性别由你自己决定是否填写；记录、忌口和爱好保存在服务器，仅用于生成你的记录、报告和推荐。退出账号或注销会按隐私政策处理。"
)

/** 使用说明正文：只读文字页，入口在个人主页和记录页。 */
@Composable
fun GuideScreen() {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 10.dp)
    ) {
        Text("随便吃 · 使用说明", fontSize = 21.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(5.dp))
        Text(
            "第一次用，按下面几步就能跑通。",
            fontSize = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        GUIDE_SECTIONS.forEach { (title, body) ->
            Spacer(Modifier.height(15.dp))
            Text(title, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(5.dp))
            Text(
                body,
                fontSize = 16.sp,
                lineHeight = 23.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Spacer(Modifier.height(26.dp))
    }
}

/** 整页使用说明：自带背景和返回，盖住底部 TAB。 */
@Composable
fun GuidePage(onBack: () -> Unit) {
    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize()) {
        AppBackground()
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 6.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                }
                Text("使用说明", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
            }
            GuideScreen()
        }
    }
}
