package com.shiji.app.data

/** 与服务端 /api/v1 对应的数据模型。字段名与 JSON 保持一致。 */

data class SmsSendRequest(val phone: String)

data class SmsSendResponse(val sent: Boolean = false, val dev_mode: Boolean = false, val code: String? = null)

data class SmsVerifyRequest(val phone: String, val code: String, val password: String? = null)

data class LoginRequest(val phone: String, val password: String)

/** 本机快速登录：用这台设备记着的设备令牌换新令牌。 */
data class DeviceLoginRequest(val device_token: String)

data class TokenResponse(val access_token: String, val device_token: String? = null)

data class Restriction(
    val id: Int,
    val keyword: String,
    val type: String = "dislike",
    /** 1 不太喜欢 / 2 感觉很难吃 / 3 完全不接受 */
    val level: Int = 3,
    val confirmed: Int = 1,
    val source: String = "manual"
)

data class Preference(
    val id: Int,
    val keyword: String,
    val weight: Double = 3.0,
    val confirmed: Int = 1,
    val source: String = "manual"
)

/** 对话里抽到、还没确认的爱好与忌口。 */
data class PendingFacts(
    val preferences: List<Preference> = emptyList(),
    val restrictions: List<Restriction> = emptyList()
)

data class SimpleOk(
    val ok: Boolean = true,
    val cleared: Boolean = false,
    val rejected: Boolean = false
)

data class Profile(
    val user_id: Int = 0,
    /** 对外展示和加好友用的 6 位码 */
    val code: String = "",
    /** 6 位码只能自己改一次；false 表示已经锁死 */
    val code_changeable: Boolean = true,
    /** 内置头像编号 avatar_1 ... avatar_7，空串就是默认首字头像 */
    val avatar: String = "",
    val gender: String = "",
    val name: String = "",
    val signature: String = "",
    val phone: String = "",
    val city: String? = null,
    val goals: List<String> = emptyList(),
    val restrictions: List<Restriction> = emptyList(),
    val preferences: List<Preference> = emptyList()
)

data class ProfileUpdate(
    val gender: String? = null,
    val avatar: String? = null,
    val name: String? = null,
    val signature: String? = null,
    val city: String? = null,
    val goals: List<String>? = null
)

data class RestrictionCreate(val type: String = "dislike", val keyword: String, val source: String = "manual")

data class MealItem(
    val id: Int = 0,
    val food_name: String = "",
    val dish_name: String? = null,
    val food_code: String? = null,
    val energy_kcal: Double? = null,
    val amount_text: String = "",
    val cooking: String = "",
    val match_status: String = "manual"
)

data class MealItemInput(
    val food_name: String,
    val dish_name: String? = null,
    val food_code: String? = null,
    val energy_kcal: Double? = null,
    val grams: Double? = null,
    val kcal_per_100g: Double? = null,
    val amount_text: String = "",
    val cooking: String = "",
    val match_status: String = "manual"
)

data class MealPhoto(
    val id: Int = 0,
    /** 七牛里的对象名，库里存的就是它 */
    val object_key: String = "",
    /** 可直接加载的完整地址（私有空间会带签名） */
    val url: String = ""
)

data class Meal(
    val id: Int = 0,
    val meal_slot: String = "",
    val meal_date: String? = null,
    val eaten_at: String = "",
    val source: String = "unknown",
    val note: String = "",
    val status: String = "confirmed",
    val items: List<MealItem> = emptyList(),
    /** 服务端返回的是带签名的临时地址，每次取记录都会重新签。 */
    val photos: List<MealPhoto> = emptyList(),
    val total_energy_kcal: Double = 0.0,
    /** 服务端发现这一餐当天已有记录时回传 true：是覆盖更新，不是新增。 */
    val replaced: Boolean? = null,
    /** 同一格已有记录时选了「追加」：内容并进了原记录，不是覆盖。 */
    val appended: Boolean? = null
)

data class MealListResponse(val items: List<Meal> = emptyList())

data class MealCreate(
    val meal_slot: String,
    val meal_date: String? = null,
    val eaten_at: String? = null,
    val source: String = "unknown",
    val note: String = "",
    val items: List<MealItemInput> = emptyList(),
    /** 同一格已经有记录时：replace 整体替换 / append 并到原记录上 */
    val mode: String = "replace"
)

data class MealPatch(
    val meal_slot: String? = null,
    val meal_date: String? = null,
    val eaten_at: String? = null,
    val source: String? = null,
    val note: String? = null,
    val items: List<MealItemInput>? = null
)


data class RecognitionRequest(
    val image_keys: List<String> = emptyList(),
    val images_base64: List<String> = emptyList(),
    val text: String = "",
    val meal_slot: String = "lunch",
    val source: String = "unknown"
)

data class EstimateRequest(
    val items: List<MealItemInput> = emptyList(),
    val meal_slot: String = "lunch"
)

/** 用户确认食材后才调估算；热量只是参考值。 */
data class EstimateResponse(
    val items: List<MealItemInput> = emptyList(),
    val energy_total_kcal: Double = 0.0,
    val engine_note: String = ""
)

data class RecognizedItem(
    val food_name: String,
    val dish_name: String? = null,
    val matched_name: String? = null,
    val food_code: String? = null,
    val energy_kcal: Double? = null,
    val amount_text: String = "",
    val cooking: String = "",
    val match_status: String = "unmatched"
)

data class RecognitionResult(
    val meal_slot: String = "lunch",
    val source: String = "unknown",
    val items: List<RecognizedItem> = emptyList(),
    val confidence: Double = 0.0,
    val note: String = ""
)

data class RecognitionResponse(val job_id: String, val result: RecognitionResult)

data class PlanItem(val food_name: String, val food_code: String? = null, val energy_kcal: Double? = null)

data class Plan(
    val title: String,
    val items: List<PlanItem> = emptyList(),
    val energy_kcal_estimate: Double = 0.0,
    val reason: String = "",
    val scene: String = "diy"
)

data class StoreInfo(val name: String, val distance_m: Int? = null, val type: String? = null)

data class RecommendRequest(
    val scene: String = "diy",
    val lat: Double? = null,
    val lng: Double? = null,
    val keyword: String? = null
)

data class RecommendResponse(
    val plans: List<Plan> = emptyList(),
    val stores: List<StoreInfo> = emptyList(),
    val note: String = "",
    val disclaimer: String = ""
)

data class CategoryShare(val category: String, val count: Int, val percent: Double)

data class TopFood(val name: String, val count: Int)

data class Report(
    val period: String,
    val days: Int,
    val meal_items: Int,
    val category_share: List<CategoryShare> = emptyList(),
    val top_foods: List<TopFood> = emptyList(),
    val gaps: List<String> = emptyList(),
    val suggestions: List<String> = emptyList(),
    val note: String = ""
)

data class ShareRequest(val type: String = "daily", val date: String? = null)

data class SharePayload(
    val type: String = "daily",
    val title: String? = null,
    val date: String? = null,
    val meals: List<SharedMeal> = emptyList(),
    val category_share: List<CategoryShare> = emptyList(),
    val has_photo: Boolean = false
)

/** 分享里的一餐：先给餐名，再给食材；不含照片、克重和热量明细。 */
data class SharedMeal(
    val meal_slot: String = "",
    val dishes: List<String> = emptyList(),
    val foods: List<String> = emptyList(),
    val eaten_at: String = "",
    /** 分享里带的照片；服务端每次读取时现签，所以地址一直有效 */
    val photos: List<SharePhoto> = emptyList(),
    val meal_date: String? = null
)

data class SharePhoto(val url: String = "")

/** 改自己的对外 ID。 */
data class CodeRequest(val code: String)

data class ShareResponse(val share_id: String, val payload: SharePayload)

data class ChatSessionResponse(val session_id: String, val notice: String = "")

data class ChatMessageRequest(
    val content: String,
    val lat: Double? = null,
    val lng: Double? = null,
    val keyword: String? = null
)

data class ChatReply(
    val reply: String,
    val extracted: List<ExtractedFact> = emptyList(),
    val likes: List<String> = emptyList(),
    val finished: Boolean = false,
    val stores: List<StoreInfo> = emptyList()
)

data class ExtractedFact(
    val id: Int = 0,
    val keyword: String = "",
    val type: String = "preference",
    val weight: Double = 3.0,
    val needs_confirm: Boolean = false
)

data class FoodSearchItem(
    val food_code: String,
    val food_name: String,
    val energy_kcal: Double,
    val energy_kj: Double? = null,
    val protein_g: Double? = null,
    val fat_g: Double? = null,
    val carb_g: Double? = null
)

data class FoodSearchResponse(val items: List<FoodSearchItem> = emptyList())

// ---------------------------------------------------------------- 广场

/** 广场里能看到的用户名片：只有昵称/签名/城市/性别和 ID，没有饮食数据。 */
data class FriendCard(
    val user_id: Int,
    /** 6 位用户码：显示和加好友都用它 */
    val code: String = "",
    /** 内置头像编号，空串用默认首字头像 */
    val avatar: String = "",
    val name: String = "",
    val signature: String = "",
    val city: String = "",
    val gender: String = "",
    val since: String? = null,
    /** none / pending_out / pending_in / friends */
    val friend_status: String = "",
    val is_friend: Boolean = false,
    val is_me: Boolean = false
)

data class FriendListResponse(val items: List<FriendCard> = emptyList())

data class FriendRequest(val code: String)

/** 加好友申请：广场那行提醒里拿到的。 */
data class FriendRequestItem(
    val request_id: Int,
    val from: FriendCard,
    val created_at: String = ""
)

data class FriendRequestListResponse(val items: List<FriendRequestItem> = emptyList())

/** 发申请后的结果：status 为 pending / friends。 */
data class FriendRequestResult(
    val ok: Boolean = true,
    val status: String = "",
    val message: String = ""
)

/** 朋友圈/私聊里的一条分享。kind 为 daily（最近一餐）或 weekly（一周占比）。 */
data class FeedPost(
    val post_id: String,
    val kind: String = "daily",
    val payload: SharePayload = SharePayload(),
    val created_at: String = "",
    val author: FriendCard,
    val mine: Boolean = false
)

data class FeedResponse(val items: List<FeedPost> = emptyList())

/** 发布/分享请求：kind 决定发"最近一餐"还是"本周占比"。 */
data class MomentRequest(val kind: String = "daily", val date: String? = null)

data class MomentResponse(val post_id: String, val payload: SharePayload = SharePayload())

/** 服务端发布的最新版本信息，用来提示用户更新。 */
data class AppVersion(
    val version_code: Int = 0,
    val version_name: String = "",
    val notes: String = "",
    val force: Boolean = false,
    val download_url: String = ""
)

data class NearbyResponse(val stores: List<StoreInfo> = emptyList())
