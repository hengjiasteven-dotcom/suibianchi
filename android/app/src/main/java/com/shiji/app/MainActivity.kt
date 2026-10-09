package com.shiji.app

import android.os.Bundle
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.LazyRow
import coil.compose.AsyncImage
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.border
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.IconButton
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.Restaurant
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import com.shiji.app.data.AlertDialogHost
import com.shiji.app.data.CheckItem
import com.shiji.app.data.ChoiceItem
import com.shiji.app.data.ApiClient
import com.shiji.app.data.Meal
import com.shiji.app.data.MealCreate
import com.shiji.app.data.MealItemInput
import com.shiji.app.data.MealPatch
import com.shiji.app.data.Plan
import com.shiji.app.data.Profile
import com.shiji.app.data.ProfileUpdate
import com.shiji.app.data.RecognitionRequest
import com.shiji.app.data.RecognizedItem
import com.shiji.app.data.RecommendRequest
import com.shiji.app.data.Report
import com.shiji.app.data.PendingFacts
import com.shiji.app.data.Preference
import com.shiji.app.data.Restriction
import com.shiji.app.data.RestrictionCreate
import com.shiji.app.data.DialogGlass
import com.shiji.app.data.LevelPicker
import com.shiji.app.data.PREFERENCE_LEVELS
import com.shiji.app.data.RESTRICTION_LEVELS
import com.shiji.app.data.preferenceDotColor
import com.shiji.app.data.preferenceLevel
import com.shiji.app.data.preferenceLevelText
import com.shiji.app.data.restrictionDotColor
import com.shiji.app.data.restrictionLevel
import com.shiji.app.data.restrictionLevelText
import com.shiji.app.data.ShareRequest
import com.shiji.app.data.MomentRequest
import com.shiji.app.data.CodeRequest
import com.shiji.app.data.FriendCard
import com.shiji.app.data.FeedPost
import com.shiji.app.data.FriendRequest
import com.shiji.app.data.FriendRequestItem
import com.shiji.app.data.TokenStore
import com.shiji.app.data.DeviceLoginRequest
import com.shiji.app.data.LoginRequest
import com.shiji.app.data.SmsSendRequest
import com.shiji.app.data.SmsVerifyRequest
import com.shiji.app.data.StoreInfo
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = GlassScheme, typography = AppTypography) {
                // 包一层 Surface：不在 Scaffold 里的页面（比如登录页）默认是黑字，深色底上会看不见
                Surface(color = Color.Transparent, contentColor = GlassScheme.onBackground) {
                    ShijiApp()
                }
            }
        }
    }


}
/** 背景图 + 毛玻璃：整体用深色配色，面板用半透明玻璃。 */
private val GlassScheme = darkColorScheme(
    primary = Color(0xFF9CC4FF),
    onPrimary = Color(0xFF10233A),
    secondary = Color(0xFFBFD4FF),
    background = Color.Transparent,
    onBackground = Color.White,
    surface = Color(0x8A14181E),
    onSurface = Color.White,
    surfaceVariant = Color(0x33FFFFFF),
    onSurfaceVariant = Color(0xE6FFFFFF),
    outline = Color(0x99FFFFFF),
    error = Color(0xFFFFB4AB)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShijiApp() {
    val scope = rememberCoroutineScope()

    var loggedIn by remember { mutableStateOf(false) }
    val context = LocalContext.current
    // 本机快速登录：冷启动先拿设备令牌换新令牌，换不回来再退回登录页
    var restoring by remember { mutableStateOf(true) }
    var canQuickLogin by remember { mutableStateOf(false) }
    var showPrivacy by remember { mutableStateOf(false) }
    var tab by remember { mutableStateOf(0) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }

    var meals by remember { mutableStateOf<List<Meal>>(emptyList()) }
    var profile by remember { mutableStateOf<Profile?>(null) }
    var plans by remember { mutableStateOf<List<Plan>>(emptyList()) }
    var stores by remember { mutableStateOf<List<StoreInfo>>(emptyList()) }
    var report by remember { mutableStateOf<Report?>(null) }

    var showRecordDialog by remember { mutableStateOf(false) }
    var editingMeal by remember { mutableStateOf<Meal?>(null) }
    var recordDaysAgo by remember { mutableStateOf(0) }
    var dayDetail by remember { mutableStateOf<String?>(null) }
    var showProfile by remember { mutableStateOf(false) }
    // 广场：Home 列表 / Moments 朋友圈 / Chat 和某好友的分享窗口
    var squareRoute by remember { mutableStateOf<SquareRoute>(SquareRoute.Home) }
    var friends by remember { mutableStateOf<List<FriendCard>>(emptyList()) }
    var friendRequests by remember { mutableStateOf<List<FriendRequestItem>>(emptyList()) }
    var moments by remember { mutableStateOf<List<FeedPost>>(emptyList()) }
    var chatPosts by remember { mutableStateOf<List<FeedPost>>(emptyList()) }
    var userCard by remember { mutableStateOf<FriendCard?>(null) }
    var recordSlot by remember { mutableStateOf("lunch") }
    var pendingEatenAt by remember { mutableStateOf<String?>(null) }
    var pendingMealDate by remember { mutableStateOf<String?>(null) }
    var pendingSlot by remember { mutableStateOf("lunch") }
    var pendingSource by remember { mutableStateOf("diy") }
    var pendingNote by remember { mutableStateOf("") }
    var pendingJob by remember { mutableStateOf<String?>(null) }
    var pendingItems by remember { mutableStateOf<List<RecognizedItem>>(emptyList()) }
    // 0 无 / 1 核对食材名称
    var recordStage by remember { mutableStateOf(0) }

    fun run(block: suspend () -> Unit) {
        scope.launch {
            busy = true
            message = ""
            try {
                block()
            } catch (e: Exception) {
                val detail = e.message ?: ""
                message = if (detail.contains("409")) {
                    "这一餐当天已经有记录了，直接改那一条就行"
                } else {
                    "操作失败：${detail.ifBlank { "网络异常" }}"
                }
            } finally {
                busy = false
            }
        }
    }

    fun loadHome() = run {
        meals = ApiClient.api.listMeals().items
        profile = ApiClient.api.getProfile()
    }

    /** 广场首页：拉好友列表。 */
    /** 广场首页要的两份数据：好友列表 + 待处理的加好友申请。 */
    suspend fun refreshPlaza() {
        friends = ApiClient.api.listFriends().items
        friendRequests = ApiClient.api.listFriendRequests().items
    }

    fun loadPlaza() = run { refreshPlaza() }

    /** 朋友圈：所有人发的分享。 */
    fun loadMoments() = run {
        moments = ApiClient.api.listMoments().items
    }

    /** 和某个好友的分享往来。 */
    fun loadChat(friendId: Int) = run {
        chatPosts = ApiClient.api.listDirect(friendId).items
    }

    /** 用设备令牌换新令牌：成功就直接进主界面。 */
    fun quickLogin() = run {
        val device = TokenStore.deviceToken
        if (device == null) {
            message = "这台手机还没有记住登录，先用验证码登录一次"
        } else {
            val token = ApiClient.api.deviceLogin(DeviceLoginRequest(device))
            TokenStore.saveLogin(token.access_token, token.device_token, TokenStore.phone)
            loggedIn = true
            loadHome()
            message = "已通过本机快速登录"
        }
    }

    // 冷启动：有设备令牌就免验证码进主界面；换不回来就留在登录页
    LaunchedEffect(Unit) {
        // 启动加载图至少显示 1 秒
        val startedAt = System.currentTimeMillis()
        TokenStore.init(context)
        val device = TokenStore.deviceToken
        canQuickLogin = device != null
        if (device != null) {
            try {
                val token = ApiClient.api.deviceLogin(DeviceLoginRequest(device))
                TokenStore.saveLogin(token.access_token, token.device_token, TokenStore.phone)
                loggedIn = true
                meals = ApiClient.api.listMeals().items
                profile = ApiClient.api.getProfile()
                message = "已通过本机快速登录"
            } catch (e: Exception) {
                message = ""
            }
        }
        val remain = 1000L - (System.currentTimeMillis() - startedAt)
        if (remain > 0) delay(remain)
        restoring = false
    }

    fun recognize(
        text: String,
        slot: String,
        source: String,
        images: List<String>,
        eatenAt: String?,
        mealDate: String?
    ) = run {
        pendingEatenAt = eatenAt
        pendingMealDate = mealDate
        pendingSlot = slot
        pendingSource = source
        val job = ApiClient.api.recognize(
            RecognitionRequest(
                text = text,
                meal_slot = slot,
                source = source,
                images_base64 = images
            )
        )
        pendingJob = job.job_id
        pendingItems = job.result.items
        pendingNote = job.result.note ?: ""
        if (pendingItems.isEmpty()) {
            pendingJob = null
            message = "没从这张图里认出食物：换一张更清晰的照片，或在输入框补一句吃了什么"
        } else {
            recordStage = 1
            message = if (images.isEmpty()) {
                "认出 ${pendingItems.size} 种食材，先核对名称"
            } else {
                "用 ${images.size} 张照片认出 ${pendingItems.size} 种食材，先核对名称"
            }
        }
    }

    fun clearPending() {
        pendingJob = null
        pendingItems = emptyList()
        pendingMealDate = null
        recordStage = 0
    }

    /** 热量是服务端后台算的：算完之前列表先显示“估算中”。 */
    fun watchEstimation(mealId: Int) {
        scope.launch {
            repeat(40) {
                delay(3000)
                val list = try {
                    ApiClient.api.listMeals().items
                } catch (e: Exception) {
                    emptyList()
                }
                if (list.isNotEmpty()) meals = list
                val mine = list.firstOrNull { it.id == mealId }
                if (mine != null && mine.status != "estimating") {
                    message = "热量已估算完成"
                    return@launch
                }
            }
            message = "热量还在估算，稍后刷新可以再看"
        }
    }

    /** 用户核对完名称就提交，不等 AI：入库后热量由服务端自动回填。 */
    fun submitPending(items: List<RecognizedItem>, note: String) {
        pendingNote = note
        val inputs = items.filter { it.food_name.isNotBlank() }.map {
            MealItemInput(
                food_name = it.food_name.trim(),
                dish_name = it.dish_name,
                amount_text = it.amount_text,
                cooking = it.cooking,
                match_status = it.match_status
            )
        }
        if (inputs.isEmpty()) {
            message = "至少要留一样食材"
            return
        }
        val jobId = pendingJob
        run {
            val body = MealCreate(
                meal_slot = pendingSlot,
                meal_date = pendingMealDate,
                source = pendingSource,
                note = pendingNote,
                eaten_at = pendingEatenAt,
                items = inputs
            )
            val meal = if (jobId != null) ApiClient.api.confirmRecognition(jobId, body)
            else ApiClient.api.createMeal(body)
            meals = ApiClient.api.listMeals().items
            // 一天四餐、每餐只留一条：同一格已有记录时是覆盖更新
            val replaced = meal.replaced == true
            message = when {
                replaced && meal.status == "estimating" -> "这一餐之前记过，已更新，热量重新估算中…"
                replaced -> "这一餐之前记过，已更新"
                meal.status == "estimating" -> "已提交，热量正在估算…"
                else -> "已记录这一餐"
            }
            clearPending()
            if (meal.status == "estimating") watchEstimation(meal.id)
        }
    }

    // 冷启动先试本机快速登录，别先闪一下登录页
    if (restoring) {
        // 打开软件时的加载图：用换下来那张旧背景，至少显示 1 秒
        SplashScreen()
        return
    }

    // 隐私政策：登录前、登录后都是整页盖住
    if (showPrivacy) {
        PrivacyPage(onBack = { showPrivacy = false })
        return
    }

    if (!loggedIn) {
        LoginScreen(
            busy = busy,
            message = message,
            canQuickLogin = canQuickLogin,
            onSendCode = { phone, onCode ->
                run {
                    val resp = ApiClient.api.sendSms(SmsSendRequest(phone))
                    onCode(resp.code)
                    message = if (resp.dev_mode) "开发模式验证码：${resp.code}" else "验证码已发送"
                }
            },
            onLogin = { phone, code, password ->
                run {
                    val token = ApiClient.api.verifySms(SmsVerifyRequest(phone, code, password.ifBlank { null }))
                    // 第一次登录就把设备令牌存下来，以后免验证码
                    TokenStore.saveLogin(token.access_token, token.device_token, phone)
                    loggedIn = true
                    meals = ApiClient.api.listMeals().items
                    profile = ApiClient.api.getProfile()
                    message = "已登录"
                }
            },
            onPasswordLogin = { phone, password ->
                run {
                    val token = ApiClient.api.loginWithPassword(LoginRequest(phone, password))
                    TokenStore.saveLogin(token.access_token, token.device_token, phone)
                    loggedIn = true
                    meals = ApiClient.api.listMeals().items
                    profile = ApiClient.api.getProfile()
                    message = "已登录"
                }
            },
            onResetPassword = { phone, code, newPassword ->
                run {
                    ApiClient.api.resetPassword(SmsVerifyRequest(phone, code, newPassword))
                    message = "密码已重置，用新密码登录吧"
                }
            },
            onQuickLogin = { quickLogin() },
            onOpenPrivacy = { showPrivacy = true }
        )
        return
    }

    BoxWithConstraints(Modifier.fillMaxSize()) {
        AppBackground()
        // 下方 TAB 栏 : 上方内容 约为 1 : 6.7
        val barHeight = (maxHeight / 7.7f).coerceIn(76.dp, 118.dp)
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.Transparent,
            topBar = {
                TopAppBar(
                    title = {
                        Text(
                            when {
                                showProfile -> "个人主页"
                                squareRoute is SquareRoute.Moments -> "朋友圈"
                                else -> titles[tab]
                            },
                            fontSize = 18.sp
                        )
                    },
                    navigationIcon = {
                        if (showProfile) {
                            IconButton(onClick = { showProfile = false }) {
                                Icon(
                                    Icons.AutoMirrored.Filled.ArrowBack,
                                    contentDescription = "返回",
                                    modifier = Modifier.size(22.dp)
                                )
                            }
                        }
                        // 朋友圈是从广场里面进去的，也给它一个返回
                        if (squareRoute is SquareRoute.Moments) {
                            IconButton(onClick = { squareRoute = SquareRoute.Home }) {
                                Icon(
                                    Icons.AutoMirrored.Filled.ArrowBack,
                                    contentDescription = "返回",
                                    modifier = Modifier.size(22.dp)
                                )
                            }
                        }
                    },
                    actions = {
                        if (!showProfile) {
                            // 右上角头像：进个人主页
                            IconButton(onClick = { showProfile = true }) {
                                Icon(
                                    Icons.Filled.AccountCircle,
                                    contentDescription = "个人主页",
                                    modifier = Modifier.size(28.dp)
                                )
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Transparent,
                        titleContentColor = Color.White
                    )
                )
            },
            bottomBar = {
                // 个人主页要盖住底部 TAB
                // 个人主页和朋友圈都要盖住底部 TAB
                if (!showProfile && squareRoute !is SquareRoute.Moments) {
                NavigationBar(
                    modifier = Modifier.height(barHeight),
                    containerColor = Color.Transparent
                ) {
                titles.forEachIndexed { index, label ->
                    NavigationBarItem(
                        selected = tab == index,
                        onClick = {
                            tab = index
                            when (index) {
                                0, 1 -> loadHome()
                                3 -> run {
                                    report = ApiClient.api.report("week")
                                    profile = ApiClient.api.getProfile()
                                }
                                4 -> {
                                    // 进广场默认回列表，并拉一次好友
                                    squareRoute = SquareRoute.Home
                                    loadPlaza()
                                }
                                else -> Unit
                            }
                        },
                        icon = { Icon(navIcons[index], contentDescription = label) },
                        label = { Text(label, fontSize = 11.sp) }
                    )
                }
            }
            }
            }
        ) { padding ->
            Box(Modifier.padding(padding).fillMaxSize()) {
            if (showProfile) {
                ProfilePage(
                    profile = profile,
                    busy = busy,
                    message = message,
                    onSaveProfile = { name, signature, city, gender ->
                        run {
                            profile = ApiClient.api.updateProfile(
                                ProfileUpdate(
                                    name = name,
                                    signature = signature,
                                    city = city,
                                    gender = gender
                                )
                            )
                            message = "资料已保存"
                        }
                    },
                    // 点头像就立即保存，不用进编辑弹窗
                    onPickAvatar = { id ->
                        scope.launch {
                            runCatching {
                                profile = ApiClient.api.updateProfile(ProfileUpdate(avatar = id))
                                message = "头像已换好"
                            }.onFailure {
                                message = "换头像失败：${it.message ?: "网络异常"}"
                            }
                        }
                    },
                    onChangeCode = { code ->
                        scope.launch {
                            runCatching {
                                profile = ApiClient.api.changeCode(CodeRequest(code))
                                message = "ID 已经改成 $code"
                            }.onFailure {
                                message = "改 ID 失败：${it.message ?: "网络异常"}"
                            }
                        }
                    },
                    onLogout = {
                        // 主动退出：连设备令牌一起清掉，下次要重新验证码
                        TokenStore.clear()
                        showProfile = false
                        loggedIn = false
                        canQuickLogin = false
                        meals = emptyList()
                        profile = null
                        message = "已退出登录"
                    },
                    onDeleteAccount = {
                        run {
                            ApiClient.api.deleteAccount()
                            TokenStore.clear()
                            showProfile = false
                            loggedIn = false
                            canQuickLogin = false
                            tab = 0
                            meals = emptyList()
                            profile = null
                            report = null
                            plans = emptyList()
                            stores = emptyList()
                            message = "账号已注销，全部记录已删除"
                        }
                    },
                    onOpenPrivacy = { showPrivacy = true }
                )
            } else if (squareRoute is SquareRoute.Moments) {
                // 朋友圈：全屏页，底部 TAB 已被盖住
                MomentsScreen(
                    posts = moments,
                    busy = busy,
                    onAvatarClick = { card -> userCard = card },
                    onShare = { kind ->
                        scope.launch {
                            runCatching {
                                ApiClient.api.postMoment(MomentRequest(kind = kind))
                                moments = ApiClient.api.listMoments().items
                                message = if (kind == "latest")
                                    "已分享最近一餐到朋友圈"
                                else
                                    "已分享本周报告到朋友圈"
                            }.onFailure {
                                message = "分享没成功：${it.message ?: "网络异常"}"
                            }
                        }
                    }
                )
            } else when (tab) {
                0 -> RecordFeedScreen(
                    meals = meals,
                    busy = busy,
                    message = message,
                    onRefresh = { loadHome() },
                    onRecord = { showRecordDialog = true }
                )
                1 -> CalendarScreen(
                    meals = meals,
                    busy = busy,
                    onRefresh = { loadHome() },
                    onDayClick = { dayDetail = it },
                    onCellClick = { date, slot ->
                        val existing = meals.firstOrNull {
                            localDateKey(it.eaten_at) == date && it.meal_slot == slot
                        }
                        if (existing != null) {
                            editingMeal = existing
                        } else {
                            val days = daysAgoOf(date)
                            if (days != null && days in 0..2) {
                                recordDaysAgo = days
                                recordSlot = slot
                                showRecordDialog = true
                            } else {
                                message = "只能补录今天、昨天、前天"
                            }
                        }
                    }
                )
                2 -> ChatScreen()
                3 -> ReportScreen(
                    report = report,
                    profile = profile,
                    // 报告里直接改程度，改完刷新一下档案
                    onSetRestrictionLevel = { item, level ->
                        scope.launch {
                            runCatching {
                                ApiClient.api.confirmRestriction(item.id, confirmed = true, level = level)
                                profile = ApiClient.api.getProfile()
                                message = "忌口「${item.keyword}」现在是${restrictionLevelText(level)}"
                            }.onFailure { message = "改程度没成功：${it.message ?: "网络异常"}" }
                        }
                    },
                    onSetPreferenceLevel = { item, level ->
                        scope.launch {
                            runCatching {
                                ApiClient.api.confirmPreference(
                                    item.id,
                                    confirmed = true,
                                    weight = level.toDouble()
                                )
                                profile = ApiClient.api.getProfile()
                                message = "爱好「${item.keyword}」现在是${preferenceLevelText(level.toDouble())}"
                            }.onFailure { message = "改程度没成功：${it.message ?: "网络异常"}" }
                        }
                    }
                )
                else -> when (val route = squareRoute) {
                    is SquareRoute.Chat -> FriendChatScreen(
                        friend = route.friend,
                        posts = chatPosts,
                        busy = busy,
                        // 退回列表时也刷一下，免得对方改过的 ID 停在旧值
                        onBack = {
                            squareRoute = SquareRoute.Home
                            loadPlaza()
                        },
                        onShare = { kind ->
                            scope.launch {
                                runCatching {
                                    ApiClient.api.sendDirect(
                                        route.friend.user_id,
                                        MomentRequest(kind = kind)
                                    )
                                    chatPosts = ApiClient.api.listDirect(route.friend.user_id).items
                                    message = "已分享给${route.friend.name.ifBlank { "好友" }}"
                                }.onFailure {
                                    message = "分享没成功：${it.message ?: "网络异常"}"
                                }
                            }
                        }
                    )
                    else -> SquareHomeScreen(
                        friends = friends,
                        requests = friendRequests,
                        busy = busy,
                        onOpenMoments = {
                            squareRoute = SquareRoute.Moments
                            loadMoments()
                        },
                        onOpenChat = { friend ->
                            squareRoute = SquareRoute.Chat(friend)
                            chatPosts = emptyList()
                            scope.launch {
                                runCatching {
                                    // 先刷一遍好友列表：对方可能改过 ID 或头像，用最新的名片
                                    val latest = ApiClient.api.listFriends().items
                                    friends = latest
                                    latest.firstOrNull { it.user_id == friend.user_id }?.let {
                                        squareRoute = SquareRoute.Chat(it)
                                    }
                                    chatPosts = ApiClient.api.listDirect(friend.user_id).items
                                }.onFailure {
                                    message = "加载聊天失败：${it.message ?: "网络异常"}"
                                }
                            }
                        },
                        // 加好友是发申请，等对方同意才成为好友
                        onAddFriend = { code ->
                            scope.launch {
                                runCatching {
                                    val result = ApiClient.api.addFriend(FriendRequest(code))
                                    refreshPlaza()
                                    message = result.message.ifBlank { "申请已发出" }
                                }.onFailure {
                                    message = "加好友失败：${it.message ?: "网络异常"}"
                                }
                            }
                        },
                        onAcceptRequest = { requestId ->
                            scope.launch {
                                runCatching {
                                    ApiClient.api.acceptFriendRequest(requestId)
                                    refreshPlaza()
                                    message = "已同意，对方现在是你的好友"
                                }.onFailure {
                                    message = "操作失败：${it.message ?: "网络异常"}"
                                }
                            }
                        },
                        onRejectRequest = { requestId ->
                            scope.launch {
                                runCatching {
                                    ApiClient.api.rejectFriendRequest(requestId)
                                    refreshPlaza()
                                    message = "已拒绝这条申请"
                                }.onFailure {
                                    message = "操作失败：${it.message ?: "网络异常"}"
                                }
                            }
                        }
                    )
                }
            }
            if (busy) {
                CircularProgressIndicator(Modifier.align(Alignment.Center))
            }
        }
        }
    }

    // 广场里点头像看到的名片（只有昵称/ID/城市/性别）
    userCard?.let { card ->
        UserCardDialog(
            card = card,
            onAddFriend = { code ->
                scope.launch {
                    runCatching {
                        val result = ApiClient.api.addFriend(FriendRequest(code))
                        refreshPlaza()
                        // 重新拉一次名片，按钮文案跟着关系变
                        userCard = ApiClient.api.publicUser(code)
                        message = result.message.ifBlank { "申请已发出" }
                    }.onFailure {
                        message = "加好友失败：${it.message ?: "网络异常"}"
                    }
                }
            },
            onDismiss = { userCard = null }
        )
    }

    if (showRecordDialog) {
        RecordDialog(
            initialDaysAgo = recordDaysAgo,
            initialSlot = recordSlot,
            onDismiss = { showRecordDialog = false },
            onSubmit = { text, slot, source, images, eatenAt, mealDate ->
                showRecordDialog = false
                recognize(text, slot, source, images, eatenAt, mealDate)
            }
        )
    }

    // 只核对食材名称；确认即提交，热量交给服务端后台估算
    if (recordStage == 1 && pendingItems.isNotEmpty()) {
        RecognitionConfirmDialog(
            items = pendingItems,
            note = pendingNote,
            onDismiss = { clearPending() },
            onConfirm = { edited, editedNote ->
                pendingItems = edited
                submitPending(edited, editedNote)
            }
        )
    }

    // 打开编辑时拉一次完整详情：列表里可能不带照片，详情才拿得到
    LaunchedEffect(editingMeal?.id) {
        val id = editingMeal?.id ?: return@LaunchedEffect
        runCatching { ApiClient.api.mealDetail(id) }.onSuccess { editingMeal = it }
    }

    editingMeal?.let { meal ->
        MealEditDialog(
            meal = meal,
            onDismiss = { editingMeal = null },
            onSave = { slot, newItems, note ->
                run {
                    // 改过名的食材没热量，服务端会标成估算中并后台重算
                    val updated = ApiClient.api.updateMeal(
                        meal.id,
                        MealPatch(
                            meal_slot = slot,
                            meal_date = meal.meal_date,
                            note = note,
                            items = newItems
                        )
                    )
                    editingMeal = null
                    meals = ApiClient.api.listMeals().items
                    if (updated.status == "estimating") {
                        message = "记录已更新，热量正在重新估算…"
                        watchEstimation(meal.id)
                    } else {
                        message = "记录已更新"
                    }
                }
            }
        )
    }

    // 日志月视图：点某一天，先看到那天的四餐
    dayDetail?.let { day ->
        val dayMeals = meals.filter { localDateKey(it.eaten_at) == day }
        val daysAgo = daysAgoOf(day)
        val canBackfill = daysAgo != null && daysAgo in 0..2
        AlertDialog(
            onDismissRequest = { dayDetail = null },
            modifier = Modifier.border(1.dp, Color(0x40FFFFFF), RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(20.dp),
            containerColor = DialogGlass,
            title = { Text(friendlyDayTitle(day)) },
            text = {
                Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
                    SLOTS.forEach { (slot, label) ->
                        val meal = dayMeals.firstOrNull { it.meal_slot == slot }
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(Color(0x1FFFFFFF))
                                .clickable {
                                    when {
                                        meal != null -> {
                                            dayDetail = null
                                            editingMeal = meal
                                        }
                                        canBackfill -> {
                                            dayDetail = null
                                            recordDaysAgo = daysAgo ?: 0
                                            recordSlot = slot
                                            showRecordDialog = true
                                        }
                                    }
                                }
                                .padding(vertical = 8.dp, horizontal = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(label, fontWeight = FontWeight.SemiBold, modifier = Modifier.width(36.dp))
                            Column(Modifier.weight(1f)) {
                                if (meal == null) {
                                    Text(
                                        "未记录",
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.outline
                                    )
                                } else {
                                    val dishes = meal.items
                                        .mapNotNull { it.dish_name?.trim()?.takeIf { name -> name.isNotBlank() } }
                                        .distinct()
                                    if (dishes.isNotEmpty()) {
                                        Text(dishes.joinToString("、"), fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                                    }
                                    Text(
                                        meal.items.joinToString("、") { it.food_name },
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.outline
                                    )
                                    Text(energyText(meal), fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                                    if (meal.note.isNotBlank()) {
                                        Text("备注：${meal.note}", fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
                                    }
                                }
                            }
                            // 用箭头暗示可以点开，不写文字说明
                            if (meal != null || canBackfill) {
                                Icon(
                                    Icons.Filled.ChevronRight,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.outline,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { dayDetail = null }) { Text("关闭") } }
        )
    }
}

/** 热量是后台估算的，没回来之前显示估算中。 */
private fun energyText(meal: Meal): String =
    if (meal.status == "estimating") "热量估算中…"
    else "约 ${meal.total_energy_kcal.toInt()} kcal（估算）"


private val titles = listOf("记录", "日志", "推荐", "报告", "广场")
private val navIcons = listOf(
    Icons.Filled.Forum,
    Icons.Filled.CalendarMonth,
    Icons.Filled.Lightbulb,
    Icons.Filled.BarChart,
    Icons.Filled.Groups
)

@Composable
fun LoginScreen(
    busy: Boolean,
    message: String,
    canQuickLogin: Boolean,
    onSendCode: (String, (String?) -> Unit) -> Unit,
    onLogin: (String, String, String) -> Unit,
    onPasswordLogin: (String, String) -> Unit,
    onResetPassword: (String, String, String) -> Unit,
    onQuickLogin: () -> Unit,
    onOpenPrivacy: () -> Unit
) {
    // 登录过的手机号带出来，省得每次手输
    var phone by remember { mutableStateOf(TokenStore.phone.orEmpty()) }
    var code by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordMode by remember { mutableStateOf(false) }
    var showReset by remember { mutableStateOf(false) }

    // 登录页也用同一张背景图 + 深色配色，避免浅底白字看不清
    Box(Modifier.fillMaxSize()) {
        AppBackground()
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            verticalArrangement = Arrangement.Center
        ) {
            Column(Modifier.fillMaxWidth().glass(20.dp).padding(20.dp)) {
                Text("随便吃", fontSize = 30.sp, fontWeight = FontWeight.Bold)
                Text("记录每一餐，吃得明白一点", fontSize = 13.sp, color = MaterialTheme.colorScheme.outline)
                Spacer(Modifier.height(20.dp))
                // 验证码为主，密码作为备用登录方式
                Row(Modifier.fillMaxWidth()) {
                    ChoiceItem("验证码登录", !passwordMode, { passwordMode = false }, Modifier.weight(1f))
                    ChoiceItem("密码登录", passwordMode, { passwordMode = true }, Modifier.weight(1f))
                }
                Spacer(Modifier.height(10.dp))

        OutlinedTextField(
            value = phone,
            onValueChange = { phone = it },
            label = { Text("手机号") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(12.dp))
        if (!passwordMode) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = code,
                onValueChange = { code = it },
                label = { Text("验证码") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            Spacer(Modifier.height(0.dp))
            OutlinedButton(
                onClick = { onSendCode(phone) { returned -> if (returned != null) code = returned } },
                enabled = !busy && phone.length >= 11,
                modifier = Modifier.padding(start = 8.dp)
            ) { Text("获取") }
        }
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("密码（首次注册时设置）") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = { onLogin(phone, code, password) },
            enabled = !busy && phone.length >= 11 && code.isNotBlank(),
            modifier = Modifier.fillMaxWidth()
        ) { Text("登录 / 注册") }
        } else {
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("密码") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(18.dp))
            Button(
                onClick = { onPasswordLogin(phone, password) },
                enabled = !busy && phone.length >= 11 && password.isNotBlank(),
                modifier = Modifier.fillMaxWidth()
            ) { Text("登录") }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = { showReset = true }, enabled = !busy) {
                    Text("忘记密码？", fontSize = 12.sp)
                }
            }
        }

        if (canQuickLogin) {
            TextButton(onClick = onQuickLogin, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                Text("本机快速登录（免验证码）", fontSize = 13.sp)
            }
        }

        if (message.isNotBlank()) {
            Spacer(Modifier.height(10.dp))
            Text(message, color = MaterialTheme.colorScheme.primary, fontSize = 13.sp)
        }

        Spacer(Modifier.height(12.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("登录即代表同意", fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            Text(
                "《隐私政策》",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.clickable { onOpenPrivacy() }
            )
        }
    }
        }
    }

    if (showReset) {
        ResetPasswordDialog(
            initialPhone = phone,
            busy = busy,
            onSendCode = onSendCode,
            onDismiss = { showReset = false },
            onConfirm = { p, c, newPwd ->
                showReset = false
                onResetPassword(p, c, newPwd)
            }
        )
    }

}
/** 背景图 + 模糊，作为毛玻璃的底。 */
@Composable
fun AppBackground() {
    Box(Modifier.fillMaxSize()) {
        Image(
            painter = painterResource(R.drawable.app_bg),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            // 只要一点点雾面，照片本身要看得清
            modifier = Modifier.fillMaxSize().blur(3.dp)
        )
        // 轻微压暗：够白字看清，又不把照片盖死
        Box(Modifier.fillMaxSize().background(Color(0x5C0B0D12)))
    }
}


/** 打开软件时的加载图：只铺旧背景这张图，不加任何文字。 */
@Composable
private fun SplashScreen() {
    Box(Modifier.fillMaxSize()) {
        Image(
            painter = painterResource(R.drawable.splash_bg),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize()
        )
        Box(Modifier.fillMaxSize().background(Color(0x660B0D12)))
        // 右下角版本号
        Text(
            "v" + BuildConfig.VERSION_NAME,
            fontSize = 12.sp,
            color = Color(0x99FFFFFF),
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(end = 20.dp, bottom = 26.dp)
        )
    }
}


/** 毛玻璃面板：半透明底（能看到背后的图）+ 细边，且保证白字读得清。 */
private fun Modifier.glass(radius: androidx.compose.ui.unit.Dp = 16.dp): Modifier = this
    .clip(RoundedCornerShape(radius))
    .background(Color(0x52101418))
    .border(1.dp, Color(0x40FFFFFF), RoundedCornerShape(radius))


/** 记录页：像聊天窗口一样的发布流，一条左一条右。 */
@Composable
fun RecordFeedScreen(
    meals: List<Meal>,
    busy: Boolean,
    message: String,
    onRefresh: () -> Unit,
    onRecord: () -> Unit
    ) {
    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                "吃过什么，都在这儿",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.weight(1f)
            )
            TextButton(onClick = onRefresh, enabled = !busy) { Text("刷新", fontSize = 12.sp) }
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (meals.isEmpty()) {
                Text(
                    "还没有记录。点下面的按钮，记下这一顿。",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.align(Alignment.Center)
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    reverseLayout = true,
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 6.dp)
                ) {
                    itemsIndexed(meals) { index, meal ->
                        MealBubble(meal = meal, rightSide = index % 2 == 0)
                    }
                }
            }
        }
        if (message.isNotBlank()) {
            Text(
                message,
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 4.dp)
            )
        }
        // 发布按钮平铺一整行
        Button(
            onClick = onRecord,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth().height(50.dp)
        ) { Text("发布这一餐", fontSize = 15.sp) }
        Spacer(Modifier.height(8.dp))
    }
}


/** 一条记录：时间 / 吃了什么 / 总能量，左一条右一条。 */
@Composable
private fun MealBubble(meal: Meal, rightSide: Boolean) {
    Box(
        Modifier.fillMaxWidth(),
        contentAlignment = if (rightSide) Alignment.CenterEnd else Alignment.CenterStart
    ) {
        Column(
            Modifier.fillMaxWidth(0.8f).glass().padding(horizontal = 12.dp, vertical = 10.dp)
        ) {
            Text(
                "${friendlyDateTime(meal.eaten_at)} · ${slotLabel(meal.meal_slot)}",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.outline
            )
            Spacer(Modifier.height(3.dp))
            // 菜品在前，下面的食材清单就是它的材料
            val dishes = meal.items
                .mapNotNull { it.dish_name?.trim()?.takeIf { name -> name.isNotBlank() } }
                .distinct()
            if (dishes.isNotEmpty()) {
                Text(
                    dishes.joinToString("、"),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(Modifier.height(2.dp))
            }
            Text(
                meal.items.joinToString("、") { it.food_name },
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.outline
            )
            Spacer(Modifier.height(3.dp))
            Text(energyText(meal), fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
            if (meal.note.isNotBlank()) {
                Text("备注：${meal.note}", fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            }
        }
    }
}



/** 爱好：名字 + 星级（点星星改）+ 确定 / 拒绝。 */
@Composable
private fun PreferenceConfirmRow(
    item: Preference,
    onConfirm: (Preference, Double) -> Unit,
    onReject: (Preference) -> Unit
) {
    var stars by remember(item.id) { mutableStateOf(item.weight.coerceIn(1.0, 5.0)) }
    Row(
        Modifier.fillMaxWidth().padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text("爱好", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline, modifier = Modifier.width(36.dp))
        Text(item.keyword, fontSize = 14.sp, modifier = Modifier.weight(1f))
        Text(
            starText(stars),
            fontSize = 14.sp,
            color = Color(0xFFE8D9B0),
            modifier = Modifier.padding(end = 4.dp).clickable {
                stars = if (stars >= 5.0) 1.0 else stars + 1.0
            }
        )
        TextButton(onClick = { onConfirm(item, stars) }) { Text("确定", fontSize = 12.sp) }
        TextButton(onClick = { onReject(item) }) { Text("拒绝", fontSize = 12.sp) }
    }
}


/** 忌口：直接定性为完全不能接受。 */
@Composable
private fun RestrictionConfirmRow(
    item: Restriction,
    onConfirm: (Restriction) -> Unit,
    onReject: (Restriction) -> Unit
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text("忌口", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline, modifier = Modifier.width(36.dp))
        Text(item.keyword, fontSize = 14.sp, modifier = Modifier.weight(1f))
        Text(
            "完全不能接受",
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.padding(end = 4.dp)
        )
        TextButton(onClick = { onConfirm(item) }) { Text("确定", fontSize = 12.sp) }
        TextButton(onClick = { onReject(item) }) { Text("拒绝", fontSize = 12.sp) }
    }
}


private fun starText(value: Double): String {
    val filled = value.coerceIn(1.0, 5.0).toInt()
    return "★".repeat(filled) + "☆".repeat(5 - filled)
}
@Composable
fun RecommendScreen(
    plans: List<Plan>,
    stores: List<StoreInfo>,
    busy: Boolean,
    onDiy: () -> Unit,
    onTakeout: () -> Unit
) {
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onDiy, enabled = !busy, modifier = Modifier.weight(1f)) { Text("自己做") }
            OutlinedButton(onClick = onTakeout, enabled = !busy, modifier = Modifier.weight(1f)) { Text("点外卖") }
        }
        Spacer(Modifier.height(12.dp))
        LazyColumn(Modifier.weight(1f)) {
            items(plans) { plan ->
                Card(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Text(plan.title, fontWeight = FontWeight.SemiBold)
                        Text(plan.items.joinToString("、") { it.food_name }, fontSize = 14.sp)
                        Text("约 ${plan.energy_kcal_estimate.toInt()} kcal", color = MaterialTheme.colorScheme.outline)
                        if (plan.reason.isNotBlank()) {
                            Text(plan.reason, fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                        }
                    }
                }
            }
            if (stores.isNotEmpty()) {
                item {
                    Text("附近可选店铺", fontWeight = FontWeight.Bold, modifier = Modifier.padding(vertical = 8.dp))
                }
                items(stores) { store ->
                    Text("· ${store.name}（${store.distance_m ?: "-"} 米）", modifier = Modifier.padding(vertical = 2.dp))
                }
            }
        }
    }
}

/** 报告里点程度就会弹这个：三个档位选一个，选完直接生效。 */
private class LevelEdit(
    val title: String,
    val options: List<Pair<Int, String>>,
    val current: Int,
    // 圆点颜色跟着档位走：爱好绿、忌口红
    val dotColor: (Int) -> Color = { Color(0xFFE8D9B0) },
    val apply: (Int) -> Unit
)


@Composable
fun ReportScreen(
    report: Report?,
    profile: Profile?,
    onSetRestrictionLevel: (Restriction, Int) -> Unit = { _, _ -> },
    onSetPreferenceLevel: (Preference, Int) -> Unit = { _, _ -> }
) {
    var levelEdit by remember { mutableStateOf<LevelEdit?>(null) }

    levelEdit?.let { edit ->
        AlertDialog(
            onDismissRequest = { levelEdit = null },
            modifier = Modifier.border(1.dp, Color(0x40FFFFFF), RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(20.dp),
            containerColor = DialogGlass,
            title = { Text(edit.title) },
            text = {
                Column {
                    Text(
                        "改完立刻生效，之后的推荐按新的程度来。",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.outline
                    )
                    Spacer(Modifier.height(12.dp))
                    LevelPicker(edit.options, edit.current, dotColor = edit.dotColor, onSelect = { level ->
                        edit.apply(level)
                        levelEdit = null
                    })
                }
            },
            confirmButton = { TextButton(onClick = { levelEdit = null }) { Text("关闭") } }
        )
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Spacer(Modifier.height(12.dp))
        LazyColumn(Modifier.weight(1f)) {
            if (report == null) {
                item {
                    Text("还没有报告。", color = MaterialTheme.colorScheme.outline, fontSize = 13.sp)
                }
            } else {
                item {
                    Text("最近 ${report.days} 天，共 ${report.meal_items} 条食材记录", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(10.dp))
                    // 类别占比：环形图 + 图例
                    CategoryShareChart(
                        shares = report.category_share,
                        total = report.meal_items
                    )
                }
                if (report.top_foods.isNotEmpty()) {
                    item {
                        Spacer(Modifier.height(16.dp))
                        Text("最常吃", fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(8.dp))
                        TopFoodBars(report.top_foods.take(6))
                    }
                }
                if (report.gaps.isNotEmpty()) {
                    item {
                        Spacer(Modifier.height(10.dp))
                        Text(
                            "需要补充：${report.gaps.joinToString("、")}",
                            color = MaterialTheme.colorScheme.primary,
                            fontSize = 13.sp
                        )
                    }
                }
                item {
                    Spacer(Modifier.height(8.dp))
                    Text(report.note, fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                }
                // 忌口是唯一长期保留的饮食约束（口味会变，只在当前对话里生效）
                val avoids = profile?.restrictions.orEmpty()
                if (avoids.isNotEmpty()) {
                    item {
                        Spacer(Modifier.height(14.dp))
                        Text("忌口", fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text(
                            "按程度来：不太喜欢的少推，很难吃和完全不接受的不进推荐",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.outline
                        )
                    }
                    items(avoids) { item ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 3.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "忌口",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.outline,
                                modifier = Modifier.width(36.dp)
                            )
                            Text(item.keyword, fontSize = 13.sp, modifier = Modifier.weight(1f))
                            LevelChip(
                                restrictionLevelText(item.level),
                                restrictionDotColor(restrictionLevel(item.level))
                            ) {
                                levelEdit = LevelEdit(
                                    "忌口 · ${item.keyword}",
                                    RESTRICTION_LEVELS,
                                    restrictionLevel(item.level),
                                    dotColor = ::restrictionDotColor
                                ) { level -> onSetRestrictionLevel(item, level) }
                            }
                        }
                    }
                }
                val likes = profile?.preferences.orEmpty()
                if (likes.isNotEmpty()) {
                    item {
                        Spacer(Modifier.height(14.dp))
                        Text("爱好", fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text(
                            "爱吃的程度也分三档，之后的推荐会优先照顾",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.outline
                        )
                    }
                    items(likes) { item ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 3.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "爱好",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.outline,
                                modifier = Modifier.width(36.dp)
                            )
                            Text(item.keyword, fontSize = 13.sp, modifier = Modifier.weight(1f))
                            LevelChip(
                                preferenceLevelText(item.weight),
                                preferenceDotColor(preferenceLevel(item.weight))
                            ) {
                                levelEdit = LevelEdit(
                                    "爱好 · ${item.keyword}",
                                    PREFERENCE_LEVELS,
                                    preferenceLevel(item.weight),
                                    dotColor = ::preferenceDotColor
                                ) { level -> onSetPreferenceLevel(item, level) }
                            }
                        }
                    }
                }
            }
        }
    }
}


/** 报告里那行程度：小胶囊，点开能改。 */
@Composable
private fun LevelChip(text: String, dotColor: Color, onClick: () -> Unit) {
    Row(
        Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(Color(0x26FFFFFF))
            .border(1.dp, Color(0x33FFFFFF), RoundedCornerShape(20.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            Modifier
                .size(7.dp)
                .clip(CircleShape)
                .background(dotColor)
        )
        Text(
            text,
            fontSize = 11.sp,
            color = Color(0xE6FFFFFF),
            modifier = Modifier.padding(start = 5.dp)
        )
        Text(" ⌄", fontSize = 11.sp, color = Color(0x99FFFFFF))
    }
}


@Composable
fun RecordDialog(
    initialDaysAgo: Int,
    initialSlot: String,
    onDismiss: () -> Unit,
    onSubmit: (String, String, String, List<String>, String?, String?) -> Unit
) {
    var text by remember(initialDaysAgo, initialSlot) { mutableStateOf("") }
    var slot by remember(initialSlot) { mutableStateOf(initialSlot) }
    var daysAgo by remember(initialDaysAgo) { mutableStateOf(initialDaysAgo) }
    var photos by remember { mutableStateOf<List<PickedPhoto>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // 一次可以加多张：相册多选、相机可以拍了再加
    fun addPhotos(uris: List<android.net.Uri>) {
        val room = (MAX_PHOTOS - photos.size).coerceAtLeast(0)
        if (uris.isEmpty() || room == 0) {
            return
        }
        loading = true
        scope.launch {
            val loaded = withContext(Dispatchers.IO) {
                uris.take(room).mapNotNull { loadImageBase64(context, it) }
                    .map { PickedPhoto(it.first, it.second) }
            }
            photos = photos + loaded
            loading = false
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        addPhotos(uris)
    }

    var pendingPhotoUri by remember { mutableStateOf<android.net.Uri?>(null) }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        val uri = pendingPhotoUri
        if (ok && uri != null) {
            addPhotos(listOf(uri))
        }
    }

    fun removePhoto(index: Int) {
        photos = photos.filterIndexed { i, _ -> i != index }
    }

    AlertDialogHost(
        title = "记录一餐",
        body = "",
        confirmText = "识别并继续",
        dismissText = "取消",
        onConfirm = {
            if (text.isNotBlank() || photos.isNotEmpty()) {
                // 不问了：这一餐从哪来交给识别去判断，用户只需要管吃了什么、什么时候
                onSubmit(
                    text,
                    slot,
                    "unknown",
                    photos.map { it.base64 },
                    backfillTimestamp(daysAgo),
                    localDateFor(daysAgo)
                )
            }
        },
        onDismiss = onDismiss,
        content = {
            Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    label = { Text("这一餐吃了什么（可选）") },
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedButton(
                        onClick = { picker.launch("image/*") },
                        enabled = !loading && photos.size < MAX_PHOTOS
                    ) { Text("选择照片") }
                    OutlinedButton(onClick = {
                        val uri = createPhotoUri(context)
                        if (uri != null) {
                            pendingPhotoUri = uri
                            cameraLauncher.launch(uri)
                        }
                    }, enabled = !loading && photos.size < MAX_PHOTOS) { Text("拍照") }
                }
                Text(
                    when {
                        loading -> "读取中…"
                        photos.isEmpty() -> "可以不加照片，纯文字也能记"
                        else -> "已选 ${photos.size} 张（最多 $MAX_PHOTOS 张）"
                    },
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.outline
                )
                photos.forEachIndexed { index, photo ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        PhotoThumb(photo.base64)
                        Spacer(Modifier.width(8.dp))
                        Text("照片 ${index + 1}", fontSize = 13.sp, modifier = Modifier.weight(1f))
                        TextButton(onClick = { removePhoto(index) }) { Text("移除") }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text("哪一天", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                Row(Modifier.fillMaxWidth()) {
                    ChoiceItem("今天", daysAgo == 0, { daysAgo = 0 }, Modifier.weight(1f))
                    ChoiceItem("昨天", daysAgo == 1, { daysAgo = 1 }, Modifier.weight(1f))
                    ChoiceItem("前天", daysAgo == 2, { daysAgo = 2 }, Modifier.weight(1f))
                }
                Spacer(Modifier.height(4.dp))
                Text("哪一餐", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                Row(Modifier.fillMaxWidth()) {
                    ChoiceItem("早餐", slot == "breakfast", { slot = "breakfast" }, Modifier.weight(1f))
                    ChoiceItem("午餐", slot == "lunch", { slot = "lunch" }, Modifier.weight(1f))
                }
                Row(Modifier.fillMaxWidth()) {
                    ChoiceItem("晚餐", slot == "dinner", { slot = "dinner" }, Modifier.weight(1f))
                    ChoiceItem("夜宵", slot == "supper", { slot = "supper" }, Modifier.weight(1f))
                }
            }
        }
    )
}

private fun slotLabel(slot: String) = when (slot) {
    "breakfast" -> "早餐"
    "lunch" -> "午餐"
    "dinner" -> "晚餐"
    "supper" -> "夜宵"
    else -> slot
}

/** 读取相册图片，最长边压到 1600 像素后转 base64，避免请求体过大。 */
private fun loadImageBase64(
    context: android.content.Context,
    uri: android.net.Uri,
    maxSide: Int = 1600
): Pair<String, String>? {
    val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return null
    val bitmap = android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return null
    val longest = maxOf(bitmap.width, bitmap.height)
    val scaled = if (longest > maxSide) {
        val ratio = maxSide.toFloat() / longest
        android.graphics.Bitmap.createScaledBitmap(
            bitmap,
            (bitmap.width * ratio).toInt().coerceAtLeast(1),
            (bitmap.height * ratio).toInt().coerceAtLeast(1),
            true
        )
    } else {
        bitmap
    }
    val out = java.io.ByteArrayOutputStream()
    scaled.compress(android.graphics.Bitmap.CompressFormat.JPEG, 85, out)
    val name = uri.lastPathSegment?.substringAfterLast('/') ?: "photo.jpg"
    return Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP) to name
}

/** 生成一个给相机写入的临时文件 URI。 */
@Composable
fun HistoryScreen(
    meals: List<Meal>,
    busy: Boolean,
    onRefresh: () -> Unit,
    onEdit: (Meal) -> Unit,
    onBackfill: () -> Unit
) {
    val grouped = meals.groupBy { localDateKey(it.eaten_at) }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onBackfill, enabled = !busy, modifier = Modifier.weight(1f)) { Text("补录一餐") }
            OutlinedButton(onClick = onRefresh, enabled = !busy, modifier = Modifier.weight(1f)) { Text("刷新") }
        }
        Spacer(Modifier.height(6.dp))
        Text("可补录今天、昨天、前天；记录只能编辑，不提供删除", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
        Spacer(Modifier.height(8.dp))
        if (grouped.isEmpty()) {
            Text("还没有记录", color = MaterialTheme.colorScheme.outline)
        } else {
            LazyColumn(Modifier.weight(1f)) {
                grouped.forEach { (day, dayMeals) ->
                    item {
                        Row(Modifier.fillMaxWidth().padding(top = 10.dp, bottom = 4.dp)) {
                            Text(friendlyDate(day), fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                            if (dayMeals.any { it.status == "estimating" }) {
                                Text("热量估算中…", color = MaterialTheme.colorScheme.outline)
                            } else {
                                Text("约 ${dayMeals.sumOf { it.total_energy_kcal }.toInt()} kcal", color = MaterialTheme.colorScheme.outline)
                            }
                        }
                    }
                    items(dayMeals) { meal ->
                        Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Column(Modifier.padding(12.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(slotLabel(meal.meal_slot), fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                                    TextButton(onClick = { onEdit(meal) }) { Text("编辑") }
                                }
                                Text(meal.items.joinToString("、") { it.food_name }, fontSize = 14.sp)
                                val dayDishes = meal.items
                                    .mapNotNull { it.dish_name?.trim()?.takeIf { name -> name.isNotBlank() } }
                                    .distinct()
                                if (dayDishes.isNotEmpty()) {
                                    Text(dayDishes.joinToString("、"), fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                                }
                                Text(energyText(meal), color = MaterialTheme.colorScheme.outline)
                                if (meal.note.isNotBlank()) {
                                    Text("备注：${meal.note}", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


@Composable
fun MealEditDialog(
    meal: Meal,
    onDismiss: () -> Unit,
    onSave: (String, List<MealItemInput>, String) -> Unit
) {
    // 按记录 ID 初始化，切换记录时会重新带出当前内容
    var slot by remember(meal.id) { mutableStateOf(meal.meal_slot) }
    var note by remember(meal.id) { mutableStateOf(meal.note) }
    var items by remember(meal.id) {
        mutableStateOf(meal.items.map { EditRow(it.food_name, it.energy_kcal, it.dish_name) })
    }

    AlertDialogHost(
        title = "编辑记录 · ${friendlyDateTime(meal.eaten_at)}",
        body = "已带出当前内容，直接改即可；记录不提供删除",
        confirmText = "保存",
        dismissText = "取消",
        onConfirm = {
            val payload = items
                .filter { it.name.isNotBlank() }
                .map {
                    MealItemInput(
                        food_name = it.name.trim(),
                        dish_name = it.dish,
                        energy_kcal = it.kcal,
                        match_status = if (it.kcal != null) "kept" else "manual"
                    )
                }
            onSave(slot, payload, note)
        },
        onDismiss = onDismiss,
        content = {
            Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
                // 这一餐当时拍的照片（服务端存在七牛，返回的是带签名的临时地址）
                if (meal.photos.isNotEmpty()) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(meal.photos) { photo ->
                            AsyncImage(
                                model = photo.url,
                                contentDescription = "这一餐的照片",
                                contentScale = ContentScale.Crop,
                                modifier = Modifier
                                    .size(84.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(Color.White.copy(alpha = 0.12f))
                            )
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                }
                Row(Modifier.fillMaxWidth()) {
                    ChoiceItem("早餐", slot == "breakfast", { slot = "breakfast" }, Modifier.weight(1f))
                    ChoiceItem("午餐", slot == "lunch", { slot = "lunch" }, Modifier.weight(1f))
                }
                Row(Modifier.fillMaxWidth()) {
                    ChoiceItem("晚餐", slot == "dinner", { slot = "dinner" }, Modifier.weight(1f))
                    ChoiceItem("夜宵", slot == "supper", { slot = "supper" }, Modifier.weight(1f))
                }
                Spacer(Modifier.height(6.dp))
                items.forEachIndexed { index, pair ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = pair.name,
                            onValueChange = { newName ->
                                val updated = items.toMutableList()
                                updated[index] = pair.copy(
                                    name = newName,
                                    kcal = if (newName == pair.name) pair.kcal else null
                                )
                                items = updated
                            },
                            label = {
                                val head = pair.dish?.takeIf { it.isNotBlank() } ?: "食材 ${index + 1}"
                                Text(
                                    if (pair.kcal != null) "$head · ${pair.kcal!!.toInt()} kcal"
                                    else "$head · 改过名，保存时重估"
                                )
                            },
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = {
                            val updated = items.toMutableList()
                            updated.removeAt(index)
                            items = updated
                        }) { Text("移除") }
                    }
                    Spacer(Modifier.height(6.dp))
                }
                TextButton(onClick = { items = items + EditRow("", null, null) }) { Text("添加食材") }
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("备注（例如：少盐、外卖）") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    )
}


/** 识别结果确认弹窗：可直接改食材名、删项、加项、改备注，改完才入库。 */
@Composable
fun RecognitionConfirmDialog(
    items: List<RecognizedItem>,
    note: String,
    onDismiss: () -> Unit,
    onConfirm: (List<RecognizedItem>, String) -> Unit
) {
    var rows by remember { mutableStateOf(items) }
    var noteText by remember { mutableStateOf(note) }

    AlertDialogHost(
        title = "核对食材",
        body = "这一步只认名字，确认后先提交。热量由服务器算完自动补上，不用等。",
        confirmText = "确认并提交",
        dismissText = "取消",
        onConfirm = { onConfirm(rows.filter { it.food_name.isNotBlank() }, noteText) },
        onDismiss = onDismiss,
        content = {
            Column(Modifier.heightIn(max = 320.dp).verticalScroll(rememberScrollState())) {
                rows.forEachIndexed { index, item ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = item.food_name,
                            onValueChange = { newName ->
                                val updated = rows.toMutableList()
                                updated[index] = updated[index].copy(food_name = newName, energy_kcal = null)
                                rows = updated
                            },
                            label = {
                                Text(item.dish_name?.takeIf { it.isNotBlank() } ?: "食材 ${index + 1}")
                            },
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = {
                            val updated = rows.toMutableList()
                            updated.removeAt(index)
                            rows = updated
                        }) { Text("移除") }
                    }
                    Spacer(Modifier.height(6.dp))
                }
                TextButton(onClick = {
                    rows = rows + RecognizedItem(food_name = "", match_status = "manual")
                }) { Text("添加食材") }
                Spacer(Modifier.height(4.dp))
                OutlinedTextField(
                    value = noteText,
                    onValueChange = { noteText = it },
                    label = { Text("备注") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    )
}




/** 一餐最多传几张照片（每张都会进模型，多了既贵又慢）。 */
private const val MAX_PHOTOS = 6


/** 已选照片：base64 数据 + 文件名。 */
private data class PickedPhoto(val base64: String, val label: String)


/** 已选照片的小缩略图。 */
@Composable
private fun PhotoThumb(base64: String) {
    val bitmap = remember(base64) {
        runCatching {
            val bytes = Base64.decode(base64, Base64.DEFAULT)
            android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
        }.getOrNull()
    }
    if (bitmap != null) {
        Image(
            bitmap = bitmap,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.size(44.dp).clip(RoundedCornerShape(6.dp))
        )
    } else {
        Box(Modifier.size(44.dp).background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(6.dp)))
    }
}


/** 编辑记录时的一行：名字 / 热量 / 原属菜品。 */
private data class EditRow(val name: String, val kcal: Double?, val dish: String?)


/** 把日期显示成今天/昨天/前天。 */
private fun friendlyDate(day: String): String {
    val fmt = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US)
    val cal = java.util.Calendar.getInstance()
    val today = fmt.format(cal.time)
    cal.add(java.util.Calendar.DAY_OF_YEAR, -1)
    val yesterday = fmt.format(cal.time)
    cal.add(java.util.Calendar.DAY_OF_YEAR, -1)
    val before = fmt.format(cal.time)
    return when (day) {
        today -> "今天"
        yesterday -> "昨天"
        before -> "前天"
        else -> day
    }
}


/** 补录时间：0 表示今天（交给服务端填当前时间）。 */
private fun backfillTimestamp(daysAgo: Int): String? {
    if (daysAgo <= 0) return null
    val cal = java.util.Calendar.getInstance()
    cal.add(java.util.Calendar.DAY_OF_YEAR, -daysAgo)
    return java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", java.util.Locale.US).format(cal.time)
}
private fun createPhotoUri(context: android.content.Context): android.net.Uri? {
    return try {
        val dir = java.io.File(context.cacheDir, "photos").apply { mkdirs() }
        val file = java.io.File(dir, "meal_${System.currentTimeMillis()}.jpg")
        FileProvider.getUriForFile(context, context.packageName + ".fileprovider", file)
    } catch (e: Exception) {
        null
    }
}


/** 找回密码：手机号 + 验证码 + 新密码，改完用新密码登录。 */
@Composable
private fun ResetPasswordDialog(
    initialPhone: String,
    busy: Boolean,
    onSendCode: (String, (String?) -> Unit) -> Unit,
    onDismiss: () -> Unit,
    onConfirm: (String, String, String) -> Unit
) {
    var phone by remember { mutableStateOf(initialPhone) }
    var code by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    val canSubmit = !busy && phone.length >= 11 && code.isNotBlank() && newPassword.length >= 6

    AlertDialogHost(
        title = "找回密码",
        body = "用手机号收验证码，把密码重置成新的。",
        confirmText = "重置密码",
        dismissText = "取消",
        onConfirm = { if (canSubmit) onConfirm(phone, code, newPassword) },
        onDismiss = onDismiss,
        content = {
            Column {
                OutlinedTextField(
                    value = phone,
                    onValueChange = { phone = it },
                    label = { Text("手机号") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = code,
                        onValueChange = { code = it },
                        label = { Text("验证码") },
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedButton(
                        onClick = { onSendCode(phone) { returned -> if (returned != null) code = returned } },
                        enabled = !busy && phone.length >= 11,
                        modifier = Modifier.padding(start = 8.dp)
                    ) { Text("获取") }
                }
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = newPassword,
                    onValueChange = { newPassword = it },
                    label = { Text("新密码（至少 6 位）") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    )
}
