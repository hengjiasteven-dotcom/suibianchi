package com.shiji.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
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

private val PRIVACY_UPDATED_AT = "2026 年 10 月 8 日"

private val PRIVACY_SECTIONS: List<Pair<String, String>> = listOf(
    "一、我们收集哪些信息" to
        "1. 账号信息：手机号（用于注册、登录、找回密码）。密码只存加密后的结果，我们不保存明文密码。\n" +
        "2. 饮食记录：你上传的照片（如果选了照片）、文字备注、餐次和时间。照片用于识别这一餐吃了什么，识别完成后按需保存到你的记录里。\n" +
        "3. 个人档案：昵称、个性签名、性别、城市，以及你在对话里确认过的忌口与爱好。\n" +
        "4. 位置信息：只有你主动点“附近店铺”时才会读取一次当前位置，用来查附近的餐厅；不点就不会读取。\n" +
        "5. 设备信息：一条设备令牌，用来实现这台手机免验证码快速登录。",
    "二、这些信息用来做什么" to
        "1. 记账与展示：把你的每一餐记下来，按日、周、月给你看吃了什么、大概多少能量。\n" +
        "2. 个性化推荐：结合你的忌口、爱好和最近吃过的内容，给出下厨或外卖的建议。\n" +
        "3. 账号安全：手机号用于登录、找回密码和识别设备。\n" +
        "我们不会把你的饮食记录、照片用于广告投放。",
    "三、AI 识别与第三方服务" to
        "1. 图片识别与热量估算：你上传的餐食照片和文字会发送给 AI 服务（DeepSeek）用于识别食材、估算热量，识别结果会先让你确认再入库。\n" +
        "2. 附近店铺：使用百度地图开放平台的按需查询能力，只查你当下要的那一次，不建立全量商家库。\n" +
        "3. 图片静态存储：如启用云存储（七牛云），照片仅用于你自己的记录展示。\n" +
        "4. 短信验证码：由阿里云号码认证服务发送；我们只把手机号交给它用于下发验证码，不用于其他用途。\n" +
        "以上第三方只在你使用对应功能时才有数据往来。",
    "四、存储与安全" to
        "1. 数据存放在我们的服务器上，传输使用加密通道。\n" +
        "2. 我们只在实现上述功能所需的范围内保留数据，你注销账号后会删除你的记录、档案与设备信息。\n" +
        "3. 请妥善保管账号密码；本机快速登录依赖设备令牌，手机转手前请先退出登录。",
    "五、你的权利" to
        "1. 查看与更正：你可以随时在“记录 / 日志”里查看、编辑每一餐的内容。\n" +
        "2. 删除：日常记录不提供删除入口，但可以随时编辑成新的内容；如果你想清空全部数据，可以注销账号。\n" +
        "3. 注销账号：在“个人主页 → 账号 → 注销账号”里操作，注销后你的记录、档案、忌口爱好与设备信息都会被删除，且无法恢复。\n" +
        "4. 位置与通知：可以随时在系统设置里关闭定位和通知权限。",
    "六、未成年人" to
        "本应用面向成年人。若你未满 18 周岁，请在监护人同意并陪同下使用。",
    "七、联系我们" to
        "如果对本政策有疑问，或希望行使上述权利，可以通过应用内的反馈渠道联系我们，我们会在合理期限内处理。",
    "八、政策更新" to
        "本政策如有调整，我们会在应用内提示。继续使用即表示你接受更新后的内容。"
)

/** 隐私政策页：只读文字页，入口在登录页和个人主页。 */
@Composable
fun PrivacyScreen() {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 10.dp)
    ) {
        Text("随便吃 · 隐私政策", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(4.dp))
        Text(
            "更新日期：$PRIVACY_UPDATED_AT",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.outline
        )
        Spacer(Modifier.height(10.dp))
        Text(
            "我们只收集让“随便吃”能正常工作的信息，下面逐条说明收集什么、用来干什么、你可以怎么管理。",
            fontSize = 15.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        PRIVACY_SECTIONS.forEach { (title, body) ->
            Spacer(Modifier.height(14.dp))
            Text(title, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            Text(
                body,
                fontSize = 15.sp,
                lineHeight = 20.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Spacer(Modifier.height(24.dp))
    }
}


/** 整页隐私政策：自带背景和返回，登录前、登录后都能盖上来。 */
@Composable
fun PrivacyPage(onBack: () -> Unit) {
    Box(Modifier.fillMaxSize()) {
        AppBackground()
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 6.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                }
                Text("隐私政策", fontSize = 19.sp, fontWeight = FontWeight.SemiBold)
            }
            PrivacyScreen()
        }
    }
}
