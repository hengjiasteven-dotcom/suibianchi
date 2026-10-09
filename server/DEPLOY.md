# 随便吃服务端部署说明

## 核心原则

**DeepSeek 的密钥只存在服务器上，App 里一个字都没有。**

链路是单向的：

```
Android App  ──(用户登录令牌)──►  你的服务器  ──(API Key 在服务端环境变量里)──►  DeepSeek
                                        │
                                        └── 本地 1198 条热量索引，负责把食材换算成热量
```

App 只知道你的服务器地址和它自己的登录令牌。就算有人把 APK 反编译，也拿不到 DeepSeek 的密钥。反过来说，**要防的不是"密钥被看到"，而是"别人拿你的接口刷额度"**——这个用下面的配额和限流来解决。

## 服务器要求

- 2 核 2G 起（识图和推理都在 DeepSeek 侧，本地只做转发和索引匹配）
- Ubuntu 22.04 / Debian 12 或同类
- 一个域名（HTTPS 需要），国内服务器还需要备案
- 开放 80 / 443；**8000 端口不要对公网开放**

## 方式一：Docker（推荐）

```bash
# 1. 安装 Docker 与 compose 插件
curl -fsSL https://get.docker.com | sh

# 2. 把项目放到服务器，比如 /opt/shiji
cd /opt/shiji

# 3. 准备环境变量
cp server/.env.example server/.env
vim server/.env            # 填 DEEPSEEK_API_KEY、SHIJI_JWT_SECRET 等
chmod 600 server/.env      # 只允许 root 读

# 4. 启动
docker compose up -d --build

# 5. 验证
curl http://127.0.0.1/health
# 期望：{"status":"ok","heat_index_count":1198,"ai_provider":"deepseek",...}
```

`ai_provider` 变成 `deepseek` 就说明密钥生效了；还是 `mock` 说明 `DEEPSEEK_API_KEY` 没读到。

### 开 HTTPS

```bash
# 用云厂商证书或 certbot
certbot certonly --webroot -w /var/www/html -d api.你的域名.com
cp /etc/letsencrypt/live/api.你的域名.com/fullchain.pem deploy/certs/
cp /etc/letsencrypt/live/api.你的域名.com/privkey.pem deploy/certs/
# 然后打开 deploy/nginx.conf 里的 443 段，注释掉 80 段，重启 nginx
docker compose restart nginx
```

## 方式二：不用 Docker（systemd + nginx）

```bash
cd /opt/shiji/server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && vim .env && chmod 600 .env
```

`/etc/systemd/system/shiji.service`：

```ini
[Unit]
Description=Shiji API
After=network.target

[Service]
WorkingDirectory=/opt/shiji/server
EnvironmentFile=/opt/shiji/server/.env
ExecStart=/opt/shiji/server/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload && systemctl enable --now shiji
```

nginx 反代直接照抄 `deploy/nginx.conf`，把 `proxy_pass http://api:8000` 改成 `http://127.0.0.1:8000`。

## 上线前检查清单

- [ ] `server/.env` 权限 600，且确认没有提交到 git（`server/.gitignore` 已忽略）
- [ ] `SHIJI_JWT_SECRET` 换成 32 位以上随机串，不要用默认值
- [ ] `SHIJI_SMS_DEV_MODE=0`，并接入真实短信服务商
- [ ] 只开 80/443，8000 只在服务器内部监听
- [ ] 开启 HTTPS，App 里 `Api.kt` 的地址改成 `https://api.你的域名.com/`
- [ ] AI 配额已生效：`SHIJI_AI_DAILY_PER_USER`（默认 100 次/人/天）、`SHIJI_AI_DAILY_TOTAL`（默认全站 2000 次/天）
- [ ] 定期备份 `data/shiji.db`（Docker 部署时是 `shiji-data` 卷）
- [ ] 日志不要记录请求体与图片内容，避免把用户饮食数据写进日志
- [ ] 密钥轮换：一旦怀疑泄露，去 DeepSeek 后台删掉旧 key 重建，改 `.env` 后重启即可

## 密钥泄露了怎么办

1. 立刻在 DeepSeek 控制台删除该 key（删掉即刻失效，比改代码快）
2. 建新 key，写进服务器 `.env`，重启服务
3. 检查 AI 用量是否有异常突增
4. 如果 key 曾经写进代码或聊天记录，视同已泄露，必须轮换

## 关于"别人拿你的接口刷你的额度"

这是服务器部署后最现实的风险，目前有两层防护：

1. **登录令牌**：`/api/v1/recognition`、`/recommendations`、`/chat/...` 都要求 Bearer token，未登录调不动
2. **调用配额**：单用户每天上限 + 全站每天上限，超了返回 429/503

再往后如果用户量上来了，可以再加：按 IP 限流（nginx `limit_req`）、图形验证码防批量注册、以及把配额计数从进程内存换成 Redis（多实例部署时必须换）。
