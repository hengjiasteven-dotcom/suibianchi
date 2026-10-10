package com.shiji.app.data

import com.shiji.app.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PATCH
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

interface ShijiApi {

    // 认证
    @POST("api/v1/auth/sms/send")
    suspend fun sendSms(@Body body: SmsSendRequest): SmsSendResponse

    @POST("api/v1/auth/sms/verify")
    suspend fun verifySms(@Body body: SmsVerifyRequest): TokenResponse

    @POST("api/v1/auth/login/password")
    suspend fun loginWithPassword(@Body body: LoginRequest): TokenResponse

    // 本机快速登录：设备令牌换访问令牌
    @POST("api/v1/auth/device/login")
    suspend fun deviceLogin(@Body body: DeviceLoginRequest): TokenResponse

    // 短信找回密码 / 注销账号
    @POST("api/v1/auth/password/reset")
    suspend fun resetPassword(@Body body: SmsVerifyRequest): SimpleOk

    @DELETE("api/v1/account")
    suspend fun deleteAccount(): SimpleOk

    // 档案
    @GET("api/v1/profile")
    suspend fun getProfile(): Profile

    @PUT("api/v1/profile")
    suspend fun updateProfile(@Body body: ProfileUpdate): Profile

    /** 改自己的 6 位 ID：只能小写字母或数字。 */
    @PUT("api/v1/profile/code")
    suspend fun changeCode(@Body body: CodeRequest): Profile

    @GET("api/v1/profile/restrictions")
    suspend fun listRestrictions(): List<Restriction>

    @POST("api/v1/profile/restrictions")
    suspend fun addRestriction(@Body body: RestrictionCreate): Restriction

    // 热量索引检索
    @GET("api/v1/foods/search")
    suspend fun searchFoods(@Query("q") keyword: String, @Query("limit") limit: Int = 10): FoodSearchResponse

    // 识别
    @POST("api/v1/recognition")
    suspend fun recognize(@Body body: RecognitionRequest): RecognitionResponse

    @POST("api/v1/recognition/{jobId}/confirm")
    suspend fun confirmRecognition(@Path("jobId") jobId: String, @Body body: MealCreate): Meal

    // 确认食材后才估算热量（识别阶段只出名称）
    @POST("api/v1/estimates")
    suspend fun estimate(@Body body: EstimateRequest): EstimateResponse

    // 记录
    @POST("api/v1/meals")
    suspend fun createMeal(@Body body: MealCreate): Meal

    @GET("api/v1/meals")
    suspend fun listMeals(): MealListResponse

    /** 单条详情：列表里字段可能不全，编辑时拉这个才拿得到照片。 */
    @GET("api/v1/meals/{mealId}")
    suspend fun mealDetail(@Path("mealId") mealId: Int): Meal

    @PATCH("api/v1/meals/{mealId}")
    suspend fun updateMeal(@Path("mealId") mealId: Int, @Body body: MealPatch): Meal

    // 推荐
    @POST("api/v1/recommendations")
    suspend fun recommend(@Body body: RecommendRequest): RecommendResponse

    @GET("api/v1/stores/nearby")
    suspend fun nearbyStores(
        @Query("lat") lat: Double,
        @Query("lng") lng: Double,
        @Query("keyword") keyword: String = "餐厅",
        @Query("limit") limit: Int = 5
    ): NearbyResponse

    // 报告
    @GET("api/v1/reports")
    suspend fun report(@Query("period") period: String): Report

    // 分享
    /** 检查更新：拿服务端发布的最新版本。 */
    @GET("api/v1/app/version")
    suspend fun appVersion(): AppVersion

    // 对话式推荐：一次会话，退出即清空
    @POST("api/v1/chat/sessions")
    suspend fun chatStart(): ChatSessionResponse

    @POST("api/v1/chat/sessions/{sid}/messages")
    suspend fun chatMessage(@Path("sid") sid: String, @Body body: ChatMessageRequest): ChatReply

    @POST("api/v1/chat/sessions/{sid}/end")
    suspend fun chatEnd(@Path("sid") sid: String): SimpleOk

    // 对话里抽到、等用户确认的爱好与忌口
    @GET("api/v1/profile/pending")
    suspend fun pendingFacts(): PendingFacts

    @PATCH("api/v1/profile/preferences/{pid}")
    suspend fun confirmPreference(
        @Path("pid") pid: Int,
        @Query("confirmed") confirmed: Boolean,
        @Query("weight") weight: Double? = null
    ): SimpleOk

    @PATCH("api/v1/profile/restrictions/{rid}")
    suspend fun confirmRestriction(
        @Path("rid") rid: Int,
        @Query("confirmed") confirmed: Boolean,
        @Query("level") level: Int? = null
    ): SimpleOk

    @POST("api/v1/shares")
    suspend fun createShare(@Body body: ShareRequest): ShareResponse

    // 广场：好友
    @GET("api/v1/friends")
    suspend fun listFriends(): FriendListResponse

    @POST("api/v1/friends")
    suspend fun addFriend(@Body body: FriendRequest): FriendRequestResult

    /** 别人申请加我、还没处理的（广场顶部那行提醒）。 */
    @GET("api/v1/friends/requests")
    suspend fun listFriendRequests(): FriendRequestListResponse

    @POST("api/v1/friends/requests/{requestId}/accept")
    suspend fun acceptFriendRequest(@Path("requestId") requestId: Int): SimpleOk

    @POST("api/v1/friends/requests/{requestId}/reject")
    suspend fun rejectFriendRequest(@Path("requestId") requestId: Int): SimpleOk

    @DELETE("api/v1/friends/{friendId}")
    suspend fun removeFriend(@Path("friendId") friendId: Int): SimpleOk

    /** 别人的公开名片：只含昵称/签名/城市/性别。 */
    @GET("api/v1/users/{userId}")
    suspend fun publicUser(@Path("code") code: String): FriendCard

    // 广场：朋友圈（所有人）
    @GET("api/v1/feed/moments")
    suspend fun listMoments(): FeedResponse

    @POST("api/v1/feed/moments")
    suspend fun postMoment(@Body body: MomentRequest): MomentResponse

    // 广场：和某个好友的一对一分享
    @GET("api/v1/feed/direct/{friendId}")
    suspend fun listDirect(@Path("friendId") friendId: Int): FeedResponse

    @POST("api/v1/feed/direct/{friendId}")
    suspend fun sendDirect(
        @Path("friendId") friendId: Int,
        @Body body: MomentRequest
    ): MomentResponse
}

object ApiClient {

    /**
     * 服务端地址，构建时注入：
     * 默认 http://10.0.2.2:8000/（模拟器访问宿主机）；
     * 真机与上线：gradlew assembleDebug -PapiBaseUrl=https://你的域名/
     */
    var baseUrl: String = BuildConfig.API_BASE_URL

    var token: String? = null

    val api: ShijiApi by lazy {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }

        val client = OkHttpClient.Builder()
            // 识图要调用大模型，默认 10 秒不够
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(90, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val builder = chain.request().newBuilder()
                token?.let { builder.addHeader("Authorization", "Bearer $it") }
                chain.proceed(builder.build())
            }
            .addInterceptor(logging)
            .build()

        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ShijiApi::class.java)
    }
}
