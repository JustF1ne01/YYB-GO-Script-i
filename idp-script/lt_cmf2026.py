# -*- coding: utf-8 -*-
# name: 联通乘风破浪2026
# cron: 0 7,20 * * *
"""
联通云盘 披荆斩棘2026(乘风破浪) 活动自动化脚本 v3.6

登录方式 (提取自 中国联通v1.1.2):
  1. Token#AppId 模式 (推荐, 免密):  export chinaUnicomCookie="a3e4c1ff2xxxxxxxxx#912d30xxxxxx"
  2. 仅 Token 模式:                 export chinaUnicomCookie="a3e4c1ff2xxxxxxxxx"
  3. 纯手机号模式 (读取本地缓存):    export chinaUnicomCookie="18600000000"
  4. 账号密码模式已失效, 仅保留手机号用于本地缓存识别
  (多账号用 & 或 换行 隔开)
  登录校验: m.client.10010.com/mobileService/onLine.htm → 换取 ecs_token
  云盘登录: getTicketByNative → /wohome/dispatcher (HandheldHallAutoLoginV2) → userToken
  Token 三级缓存复用 (默认 unicom_token_cache.json, 按账号独立存储):
    一级 缓存userToken有效 → 0次登录请求 (活动域轻量校验+滑动续期, 日常任务基本不再触发登录)
    二级 缓存ecs_token有效 → 免onLine, 仅 ticket+AutoLoginV2 (2次请求)
    三级 缓存不可用 → 完整登录链 onLine→ticket→AutoLoginV2 (3次请求)
  (ONLINE 72h / CLOUD 12h TTL, 均可用环境变量调整)

乘风破浪/披荆斩棘2026 活动协议:
  - 活动页: https://panservice.mail.wo.cn/h5/activitymobile/cmf2026/home
  - activityId: NDA= (base64 "40", 可用 UNICOM_CMF_ACTIVITY_ID 覆盖)
  - 签名: HMAC-SHA256, 参数字典按 key 排序拼接 k=v&...&secret=<SECRET>
  - 每日打卡: /activity/islandWaves/task2/checkin/panel + /submit (key=activity:island:activate)
  - 芒果TV AI视频: /api-user/api/user/ticket → mgcact.api.mgtv.com/api/cu/login
                   → video/template/submit → video/template/result 轮询
                   选图: 候选照片随机打乱 (不按顺序) 逐一尝试, 某张识别不过自动换下一张直到通过;
                   任务结束后删除本次上传到云盘的临时人脸照 (DeleteFile, 防止网盘存满)
  - 抽奖: /activity/lottery/lottery-times 查次数 → /activity/lottery 循环抽奖 (key=activity:lottery)
  - 云盘删除: POST /wohome/dispatcher key=DeleteFile
          body.param = AES-128-CBC(json, key=userToken[:16], IV=wNSOYIB1k1DjY5lA) → base64
          明文: {"spaceType":"0","vipLevel":"0","dirList":[],"fileList":[fid,...],"clientId":"1001000003"}
          header.sign = MD5(key+resTime+reqSeq+channel+version); 成功: RSP.RSP_CODE=="0000" (移入回收站)
  - 历史奖品: POST /activity/aiRole/userDrawRecords → 与本地缓存合并, 每账号保留最近3条
  - 手机号: 来自配置或 onLine 的 desmobile, 会写入 token 缓存 (缓存登录路径自动恢复)
  - PUSH_PLUS_TOKEN 推送中奖详情 (含奖品名/类型/兑换码)

环境变量:
  chinaUnicomCookie        必填, 账号配置 (见上)
  PUSH_PLUS_TOKEN          pushplus 推送 token (不填则仅控制台输出), 汇总表格推送 (30账号约7千~1.5万字符):
                           账号 / 手机号 / 签到 / 挂机值·排名·地区 / 中奖记录(最近3条, 含兑换码与时间),
                           异常账号在签到列显示失败原因; 完整过程详情以控制台日志为准
  PUSH_PLUS_TOPIC          可选, pushplus 群组编码 (一对多推送)

  ── 其他 ──
  UNICOM_CMF_ACTIVITY_ID   可选, 活动 ID (默认 NDA=)
  UNICOM_CMF_TEMPLATE_ID   可选, 芒果模板 ID (默认 2104457184351981568)
  UNICOM_CMF_IMG_FID       可选, 指定云盘人脸图片 FID (也可用旧变量 UNICOM_YPHD_MGTV_IMG_FID)
  UNICOM_CMF_LOCAL_IMAGES  可选, 本地人脸图片路径 (逗号分隔, 支持中文逗号), 上传到云盘后
                           优先用于芒果AI视频; 不填时优先读取脚本目录 face_images/ 下的
                           图片 (随脚本拷贝即可用), 再回退内置的 6 张模板图路径
  UNICOM_CMF_DEL_CLOUD_PHOTOS 可选, 填 0 关闭"删除网盘照片"步骤 (默认开启: 芒果AI视频任务后
                           自动删除脚本历史上传到云盘的临时人脸照, 防止网盘被存满; 覆盖
                           cmfface_ 前缀与本地模板图原文件名/重命名变体 "xxx(1).jpg" 等旧版遗留,
                           用户自己上传的照片不会误删; 文件移入回收站, 本地原图不受影响,
                           下次运行会重新上传)
  UNICOM_TOKEN_CACHE_PATH  可选, token 缓存文件路径 (默认脚本同目录 unicom_token_cache.json,
                           按账号独立条目存储 token_online/ecs_token/userToken, 校验通过自动续期)
  UNICOM_PRIZE_CACHE_PATH  可选, 中奖记录缓存文件 (默认脚本同目录 unicom_prize_cache.json,
                           每账号保留最近3条, 与 POST /activity/aiRole/userDrawRecords 历史合并,
                           推送中奖列展示)
  UNICOM_PRIZE_HISTORY     可选, 填 0 关闭历史奖品查询与缓存 (默认开启)
  UNICOM_TOKEN_TTL_HOURS   可选, token_online 缓存有效期 (默认 72 小时)
  UNICOM_CLOUD_TTL_HOURS   可选, 云盘 userToken/ecs_token 缓存有效期 (默认 12 小时, 校验通过滑动续期)
  chinaUnicomUuid          可选, 固定设备 UUID
  UNICOM_TEST_MODE         可选, 填 query 仅查询不执行任务
  UNICOM_PROXY_API         可选, 代理提取链接 (http/socks5)
  UNICOM_PROXY_TYPE        可选, 代理类型 (默认 socks5)

依赖: pip install requests pycryptodome
      (pycryptodome 用于云盘图片上传等接口的参数加解密)
定时建议: 0 7,20 * * * (每天 7 点 / 20 点各跑一次)
"""
import os
import sys
import re
import json
import time
import random
import hashlib
import hmac
import base64
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs, quote, unquote

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import urllib3
urllib3.disable_warnings()

SCRIPT_VERSION = "v3.6"

# ========================================
# 常量
# ========================================
YPHD_SECRET_KEY = "s8Hf3LqP9xN2vM5bR7tY1wZ4cA6eG0K"
YPHD_ACTIVITY_ID = os.environ.get("UNICOM_CMF_ACTIVITY_ID", "NDA=").strip() or "NDA="
YPHD_MGTV_TEMPLATE_ID = os.environ.get("UNICOM_CMF_TEMPLATE_ID", "2104457184351981568").strip()
YPHD_MGTV_BASE = "https://mgcact.api.mgtv.com"
YPHD_MGTV_IMG_FID = os.environ.get("UNICOM_CMF_IMG_FID", os.environ.get("UNICOM_YPHD_MGTV_IMG_FID", "")).strip()

# 云盘 upload2C 上传接口 AES 加密 (提取自 v1.1.2 hometown_upload): key=userToken[:16], IV 固定
UPLOAD_AES_IV = "wNSOYIB1k1DjY5lA"
UPLOAD_URL = "https://du.smartont.net:8443/openapi/client/upload2C"
# 本地人脸模板图: 优先读取脚本目录 face_images/ 下的图片
DEFAULT_LOCAL_FACE_IMAGES = []
_local_raw = os.environ.get("UNICOM_CMF_LOCAL_IMAGES", "").replace("，", ",").strip()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _local_raw:
    _img_paths = [p.strip() for p in _local_raw.split(",") if p.strip()]
else:
    # 默认: 优先脚本目录 face_images/ 内的图片 (随脚本拷贝到青龙等环境即可用)
    _img_dir = os.path.join(SCRIPT_DIR, "face_images")
    _img_paths = (sorted(os.path.join(_img_dir, f) for f in os.listdir(_img_dir)
                         if f.lower().endswith((".jpg", ".jpeg", ".png")))
                  if os.path.isdir(_img_dir) else [])
    if not _img_paths:
        _img_paths = DEFAULT_LOCAL_FACE_IMAGES
# 相对路径按脚本目录解析
LOCAL_FACE_IMAGES = [p if os.path.isabs(p) else os.path.join(SCRIPT_DIR, p)
                     for p in _img_paths]

# 签名接口与 getTimestamp key 的映射
SIGN_KEY_LOTTERY = "activity:lottery"            # /activity/lottery
SIGN_KEY_ISLAND = "activity:island:activate"     # 打卡 panel/submit 与 peakValue/detail
SIGN_KEY_BIND = "activity:isLand:invite"         # 绑定接口 (注意 isLand 大写L, 与页面JS一致)

# 用户标识加解密 (AES-128-CBC) — 提取自 share 落地页 JS (v.a.encrypt)
UID_AES_KEY = "GWI21sdtBTU48egd"
UID_AES_IV = "wNSOYIB1k1DjY5lA"
SHARE_TOUCHPOINT = "300500030006"
SHARE_ACTIVITY_NAME = "联通云盘披荆斩棘2026"
# 活动备用入口 (base64 编码存放)
_FALLBACK_ENTRY = base64.b64decode("aHR0cHM6Ly9wYW4ud28uY24vcy8xajFuNmQ4NzEwNg==").decode()
SHARE_CREATE_ON = os.environ.get("UNICOM_CMF_SHARE_CREATE", "1").strip() not in ("0", "false", "False")
EXTRA_CFG_RAW = os.environ.get("UNICOM_CMF_HELP_ID", "").strip()
PAIR_CFG_RAW = os.environ.get("UNICOM_CMF_HELP_PAIRS", "").strip()

BASE = "https://panservice.mail.wo.cn"
ACT_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko)  unicom{version:iphone_c@13.0100};ltst;OSVersion/18.7.8")
APP_UA = "Dalvik/2.1.0 (Linux; U; Android 12; Mi 10 Pro MIUI/21.11.3);unicom{version:android@11.0802}"

TOKEN_CACHE_PATH = os.environ.get("UNICOM_TOKEN_CACHE_PATH",
                                  os.path.join(os.path.dirname(os.path.abspath(__file__)), "unicom_token_cache.json"))
# 缓存TTL(小时): 云盘Token校验通过后滑动续期, 每日定时任务可长期免登录 (减少风控)
ONLINE_TTL_MS = int(os.environ.get("UNICOM_TOKEN_TTL_HOURS", "72")) * 3600 * 1000    # token_online 缓存有效期
CLOUD_TTL_MS = int(os.environ.get("UNICOM_CLOUD_TTL_HOURS", "12")) * 3600 * 1000     # userToken/ecs_token 缓存有效期
# 历史奖品记录缓存: GET /activity/v1/recordList (H5中奖记录页同源) → 每账号保留最近3条
PRIZE_CACHE_PATH = os.environ.get("UNICOM_PRIZE_CACHE_PATH",
                                  os.path.join(os.path.dirname(os.path.abspath(__file__)), "unicom_prize_cache.json"))
PRIZE_HISTORY_ON = os.environ.get("UNICOM_PRIZE_HISTORY", "1").strip() not in ("0", "false", "False")
# 芒果AI视频任务后自动删除脚本上传到云盘的临时人脸照 (默认开启, 防网盘存满)
DEL_CLOUD_PHOTOS_ON = os.environ.get("UNICOM_CMF_DEL_CLOUD_PHOTOS", "1").strip() not in ("0", "false", "False")
# 脚本上传的远端临时照片统一文件名前缀 (local_face_fids 的 cmfface_{idx}_), 清理时仅匹配此前缀
CLOUD_TEMP_PHOTO_PREFIX = "cmfface_"
TEST_MODE = os.environ.get("UNICOM_TEST_MODE", "").strip().lower() == "query"


def mask_str(s):
    s = str(s or "")
    if len(s) == 11 and s.isdigit():
        return s[:3] + "****" + s[7:]
    if len(s) > 8:
        return s[:4] + "****" + s[-4:]
    return s


def safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def pretty(data):
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


def response_summary(data):
    if isinstance(data, dict):
        meta = data.get("meta") or {}
        if meta:
            return f"[{meta.get('code')}] {meta.get('message')}"
        return pretty(data)[:200]
    return str(data)[:200]


def uid_encrypt(phone):
    """手机号 → 用户标识 (AES-128-CBC)"""
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError:
        return None
    cipher = AES.new(UID_AES_KEY.encode(), AES.MODE_CBC, UID_AES_IV.encode())
    return base64.b64encode(cipher.encrypt(pad(str(phone).encode(), AES.block_size))).decode()


def uid_decrypt(value):
    """用户标识 → 手机号 (解密失败返回空)"""
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except ImportError:
        return ""
    try:
        raw = base64.b64decode(value)
        cipher = AES.new(UID_AES_KEY.encode(), AES.MODE_CBC, UID_AES_IV.encode())
        return unpad(cipher.decrypt(raw), AES.block_size).decode()
    except Exception:
        return ""


def resolve_uid(raw):
    """配置项 → 用户标识 (支持完整链接/hash路由(#后?)/URL编码/裸标识值)"""
    raw = str(raw or "").strip()
    if not raw:
        return ""
    # 全串搜索参数值: 兼容普通query、hash路由(?位于#后)与编码形式
    m = re.search(r"inviterUserId(?:%3D|=)([^&\s#]+)", raw, re.IGNORECASE)
    if m:
        val = m.group(1)
        for _ in range(2):  # 最多解码两次: %3D%3D → ==
            dec = unquote(val)
            if dec == val:
                break
            val = dec
        return val.strip()
    # 无参数形式的裸值: 仅接受 base64/手机号特征, 绝不把 URL 当标识值
    if not raw.lower().startswith("http") and re.fullmatch(r"[A-Za-z0-9+/=%]+", raw):
        return raw
    # 短链 (pan.wo.cn/s/xxx): 302 Location 或页面内提取标识值
    if re.match(r"https?://[\w.-]+/s/", raw, re.IGNORECASE):
        try:
            res = requests.get(raw, allow_redirects=False, timeout=10,
                               headers={"User-Agent": APP_UA}, verify=False)
            loc = res.headers.get("Location", "") or ""
            candidates = [loc] if loc else []
            if not candidates:
                candidates = [res.text[:6000]]  # JS跳转兜底: 从页面内容提取
            for cand in candidates:
                m2 = re.search(r"inviterUserId(?:%3D|=|\\u003D)([^&\s\"'#\\]+)", cand, re.IGNORECASE)
                if m2:
                    val = m2.group(1)
                    for _ in range(2):
                        dec = unquote(val)
                        if dec == val:
                            break
                        val = dec
                    return val.strip()
                if loc and re.match(r"https?://", loc) and loc != raw:
                    return resolve_uid(loc)  # 短链二跳
        except Exception:
            pass
    return ""


class FailoverSession:
    """requests.Session 封装: 可选代理故障转移 (来自 v1.1.2)"""

    RETRIABLE_KEYWORDS = ("Max retries exceeded", "timed out", "connection",
                          "SOCKS", "ProxyError", "ConnectionError", "SSLError", "SSLEOF")

    def __init__(self, owner):
        self._session = requests.Session()
        self._session.verify = False
        self._session.headers.update({"User-Agent": APP_UA, "Connection": "keep-alive"})
        self._owner = owner

    def __getattr__(self, name):
        return getattr(self._session, name)

    def _should_failover(self, err_msg):
        if not os.environ.get("UNICOM_PROXY_API"):
            return False
        err_lower = err_msg.lower()
        return any(kw.lower() in err_lower for kw in self.RETRIABLE_KEYWORDS)

    def request(self, method, url, **kwargs):
        try:
            return self._session.request(method, url, timeout=kwargs.pop("timeout", 20), **kwargs)
        except Exception as e:
            if self._should_failover(str(e)):
                self._owner.log(f"⚠️ [故障转移] {url} 请求异常: {e}")
                self._owner.configure_proxy(force=True)  # 强制换新代理
                try:
                    return self._session.request(method, url, timeout=20, **kwargs)
                except Exception as retry_err:
                    self._owner.log(f"⚠️ [故障转移] 重试仍异常: {retry_err}")
                    return None
            raise

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


class CloudUser:
    def __init__(self, index, config_str):
        self.index = index
        self.valid = False
        self.notify_logs = []
        self.session = FailoverSession(self)
        self.account_mobile = ""
        self.mobile = ""
        self.account_password = ""
        self.token_online = ""
        self.appId = ""
        self.ecs_token = ""
        self.userToken = ""        # 云盘 H5 token
        self.uuid = os.environ.get("chinaUnicomUuid") or random_string(32)
        self.prizes = []           # 本次抽奖中奖详情
        self.prize_records = []    # 推送用: 最近3条中奖记录 (历史接口+本次合并, 按账号缓存)
        self.checkin_info = ""     # 推送用: 签到简要状态 (精简推送, 控制字数)
        self.hang_value = ""       # 推送用: 挂机值
        self.hang_rank = ""        # 推送用: 排名
        self.hang_region = ""      # 推送用: 地区 (省+市)
        self.rows = []             # 推送表格行 [(项目, 详情)]
        self.extra_targets = []    # 前置任务目标 [(描述, 标识值)]
        self.share_url = ""        # 内部预留字段
        self.joined = False        # 是否已参与活动 (checkActivityStatus state=1)
        self.status_checked = False  # 缓存校验时已查询活动状态 → run_activity 复用免重复请求
        self.status_ok = False
        self._proxy_ready = False  # 代理懒加载标记: 轮到本账号运行时才提取
        self.init_account(config_str)

    @property
    def inviter_id(self):
        """本账号的用户标识 (手机号 AES 加密, 需 pycryptodome)"""
        if not getattr(self, '_inviter_id', None):
            phone = self.mobile or self.account_mobile
            if phone:
                self._inviter_id = uid_encrypt(phone)
        return getattr(self, '_inviter_id', None) or ""

    # ---------- 基础 ----------
    def log(self, msg, notify=False):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] 账号[{self.index}]{msg}"
        print(line)
        if notify:
            self.notify_logs.append(str(msg))

    def row(self, item, detail, log=None):
        """记录推送表格行; 传 log 时同时输出控制台日志"""
        self.rows.append((str(item), str(detail)))
        if log:
            self.log(log)

    def init_account(self, config_str):
        parts = config_str.split('#')
        if len(parts) >= 2 and len(parts[0]) == 11 and parts[0].isdigit() and len(parts[1]) < 50:
            # 手机号#密码 (密码登录已失效, 保留手机号用于缓存)
            self.account_mobile = parts[0]
            self.account_password = parts[1]
            self.log("识别到手机号#密码模式: 密码登录已失效, 将尝试本地缓存 Token")
        else:
            self.token_online = parts[0].strip()
            if len(self.token_online) == 11 and self.token_online.isdigit():
                self.account_mobile = self.token_online
                self.token_online = ""
                self.log(f"识别到纯手机号模式: {mask_str(self.account_mobile)} (读取本地缓存)")
            if len(parts) > 1 and parts[1].strip():
                self.appId = parts[1].strip()
            if len(parts) > 2 and parts[2].strip().isdigit() and len(parts[2].strip()) == 11:
                self.account_mobile = parts[2].strip()

    def configure_proxy(self, force=False):
        """提取代理 (懒加载): 每个账号轮到运行时才提取一次, 不启动时批量提取.
        force=True 用于请求故障转移时强制换新代理."""
        if not force and self._proxy_ready:
            return
        proxy_api = os.environ.get("UNICOM_PROXY_API")
        if not proxy_api:
            return
        proxy_type = os.environ.get("UNICOM_PROXY_TYPE", "socks5").lower()
        for attempt in range(1, 4):
            try:
                if attempt > 1:
                    time.sleep(2)
                res = requests.get(proxy_api, timeout=10)
                m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[:\s\t]+(\d{1,5})', res.text)
                if not m:
                    continue
                ip, port = m.group(1), m.group(2)
                proxy_url = f"{proxy_type}://{ip}:{port}"
                requests.get("https://www.baidu.com", proxies={"http": proxy_url, "https": proxy_url}, timeout=3)
                self.session.proxies.update({"http": proxy_url, "https": proxy_url})
                self._proxy_ready = True
                self.log(f"✅ 代理生效: {proxy_url}")
                return
            except Exception:
                continue
        if force:
            self.log("🚫 故障转移: 代理重新提取失败, 沿用原配置重试")
        else:
            self._proxy_ready = True  # 提取失败回退本地 IP, 本账号不再反复请求提取接口
            self.log("🚫 代理提取失败, 回退本地 IP")

    # ---------- 登录 (三级缓存复用, 登录链提取自 v1.1.2) ----------
    def _cache_keys(self):
        """缓存键: 手机号优先 (兼容旧缓存); 无手机号用 token 摘要 (Token#AppId 免密模式)"""
        keys = []
        phone = self.account_mobile or self.mobile
        if phone:
            keys.append(str(phone))
        if self.token_online:
            keys.append("tok:" + hashlib.md5(self.token_online.encode()).hexdigest()[:12])
        return keys

    def restore_phone_from_cache(self):
        """从 token 缓存恢复手机号 (缓存登录路径不经过 onLine, 手机号来自历史 onLine 的 desmobile)"""
        keys = self._cache_keys()
        if not keys or not os.path.exists(TOKEN_CACHE_PATH):
            return False
        try:
            with open(TOKEN_CACHE_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            return False
        for k in keys:
            e = cache.get(k)
            if isinstance(e, dict) and e.get('phone'):
                self.account_mobile = self.account_mobile or str(e['phone'])
                self.mobile = self.mobile or str(e['phone'])
                return True
        return False

    def _ensure_phone(self):
        """一/二级缓存登录成功后补齐手机号: 先读缓存, 缺失则一次性补走 onLine (此后入缓存, 长期0成本)"""
        if self.mobile or self.account_mobile:
            return
        if self.restore_phone_from_cache():
            return
        self.log("🩹 缓存登录缺少手机号(部分活动功能需要), 一次性补走 onLine 获取...")
        if self.on_line():
            self.save_token_to_cache()

    def ensure_login(self, max_attempts=3):
        """三级策略: ①缓存userToken直用(0次登录请求) → ②缓存ecs_token换票(2次) → ③完整登录链(3次)
        日常定时任务基本命中一级, 大幅减少 onLine/getTicket/AutoLogin 等登录类请求 (降低风控)"""
        self.configure_proxy()  # 轮到本账号时才提取代理 (懒加载)
        self.load_token_from_cache()
        # 一级: 缓存的云盘 userToken 直用 → 0 次登录请求 (活动域轻量校验 + 滑动续期)
        if self.userToken and self.validate_cloud_token():
            self.touch_cloud_cache()
            self._ensure_phone()
            return True
        self.userToken = ""  # 缓存失效, 走登录链
        # 二级: 缓存的 ecs_token 仍有效 → 免 onLine 直接换云盘Token (2 次请求)
        # ticket_attempts=1: 缓存ecs已死时快速失败, 不浪费重试 (三级登录链兜底)
        if self.ecs_token and self.cloud_login(quiet=True, ticket_attempts=1):
            self.save_token_to_cache()
            self._ensure_phone()
            return True
        # 三级: 完整登录链 onLine → getTicketByNative → AutoLoginV2 (3 次请求, 仅缓存不可用时)
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                self.log(f"🔄 登录重试 {attempt}/{max_attempts}")
            if not self.token_online:
                if self.account_password:
                    self.log("账号密码登录已失效, 未找到可用 Token, 跳过")
                else:
                    self.log("❌ 无可用 Token (配置或缓存均未提供), 跳过")
                return False
            if self.on_line():
                self.save_token_to_cache()
                if self.cloud_login():
                    self.save_token_to_cache()  # 按账号更新缓存 (含 ecs_token/userToken)
                    return True
            if attempt < max_attempts:
                time.sleep(2)
        return False

    def validate_cloud_token(self):
        """轻量校验缓存 userToken 是否仍有效 (活动域普通查询接口, 非登录接口, 不触发风控计数)"""
        data = self.act_get("/activity/checkActivityStatus", {"activityId": YPHD_ACTIVITY_ID})
        meta = data.get("meta") or {}
        code = str(meta.get("code") or "")
        msg = str(meta.get("message") or "")
        if code == "-1":  # 请求异常(网络/超时): 不判定 token 失效, 乐观复用
            self.log("⚠️ 缓存校验请求异常, 仍尝试使用缓存Token")
            return True
        if code == "200":
            self.status_ok = self._apply_activity_status(data)  # 顺带完成活动状态查询, run_activity 复用
            self.status_checked = True
            self.log("♻️ [缓存复用] 云盘Token有效, 跳过登录链 (减少风控)")
            return True
        if code in ("401", "403", "40101", "40001", "40401") or \
                any(k in msg for k in ("登录", "token", "Token", "授权", "身份", "失效")):
            self.log(f"⚠️ 缓存云盘Token已失效[{code}]{msg[:40]}, 转登录链")
            return False
        # 其他业务码 (如活动结束等): token 本身有效, 交由活动流程正常处理
        self.log(f"ℹ️ 缓存校验业务码[{code}]{(':' + msg[:40]) if msg else ''}, Token视为有效")
        return True

    def touch_cloud_cache(self):
        """校验通过后滑动续期: 仅更新本账号缓存条目的时间戳 (不动其他账号)"""
        keys = self._cache_keys()
        if not keys:
            return
        try:
            cache = {}
            if os.path.exists(TOKEN_CACHE_PATH):
                with open(TOKEN_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
        except Exception:
            return
        now = datetime.now()
        updated = False
        for k in keys:
            entry = cache.get(k)
            if isinstance(entry, dict) and entry.get("userToken"):
                entry["ts_cloud"] = int(now.timestamp() * 1000)
                entry["cloud_time"] = now.strftime('%Y-%m-%d %H:%M:%S')
                updated = True
        if not updated:
            return
        try:
            with open(TOKEN_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"❌ 缓存续期失败: {e}")

    def load_token_from_cache(self):
        keys = self._cache_keys()
        if not keys or not os.path.exists(TOKEN_CACHE_PATH):
            return False
        try:
            with open(TOKEN_CACHE_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            return False
        entry = None
        for k in keys:
            if isinstance(cache.get(k), dict):
                entry = cache[k]
                break
        if not entry:
            return False
        now_ms = time.time() * 1000
        loaded = False
        # token_online/appId: 配置未提供时用缓存补齐 (TTL 默认 72h)
        if not self.token_online and entry.get('token_online'):
            if now_ms - entry.get('timestamp', 0) < ONLINE_TTL_MS:
                self.token_online = entry['token_online']
                self.appId = entry.get('appId') or self.appId
                self.log(f"♻️ [缓存] 加载 token_online ({entry.get('time')})")
                loaded = True
        # 云盘凭据 ecs_token/userToken (TTL 默认 12h, 校验通过后滑动续期)
        if entry.get('ts_cloud') and now_ms - entry['ts_cloud'] < CLOUD_TTL_MS:
            if entry.get('userToken') and not self.userToken:
                self.userToken = entry['userToken']
                self.log(f"♻️ [缓存] 加载云盘 userToken ({entry.get('cloud_time')})")
                loaded = True
            if entry.get('ecs_token') and not self.ecs_token:
                self.ecs_token = entry['ecs_token']
                loaded = True
        return loaded

    def save_token_to_cache(self):
        keys = self._cache_keys()
        if not keys:
            return
        try:
            cache = {}
            if os.path.exists(TOKEN_CACHE_PATH):
                with open(TOKEN_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
        except Exception:
            cache = {}
        now = datetime.now()
        now_ms = int(now.timestamp() * 1000)
        entry = {}
        for k in keys:  # 沿用本账号已有条目字段 (其他账号不受影响)
            if isinstance(cache.get(k), dict):
                entry = dict(cache[k])
                break
        entry.update({
            "token_online": self.token_online or entry.get("token_online", ""),
            "appId": self.appId or entry.get("appId", ""),
            "timestamp": now_ms,                    # token_online 校验时间
            "time": now.strftime('%Y-%m-%d %H:%M:%S'),
        })
        if self.account_mobile or self.mobile:      # 手机号入缓存 (部分活动功能依赖)
            entry["phone"] = str(self.account_mobile or self.mobile)
        # 云盘凭据: 值变化时才刷新 ts_cloud (滑动续期基准)
        if self.ecs_token and self.ecs_token != entry.get("ecs_token"):
            entry["ecs_token"] = self.ecs_token
            entry["ts_cloud"] = now_ms
            entry["cloud_time"] = entry["time"]
        if self.userToken and self.userToken != entry.get("userToken"):
            entry["userToken"] = self.userToken
            entry["ts_cloud"] = now_ms
            entry["cloud_time"] = entry["time"]
        for k in keys:  # 同一账号所有别名键 (手机号/token摘要) 写同一份, 下次任一命中
            cache[k] = entry
        try:
            with open(TOKEN_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"❌ 保存缓存失败: {e}")

    def on_line(self):
        if not self.token_online:
            return False
        try:
            url = "https://m.client.10010.com/mobileService/onLine.htm"
            data = {
                'isFirstInstall': '1',
                'netWay': 'Wifi',
                'version': 'android@11.0000',
                'token_online': self.token_online,
                'provinceChanel': 'general',
                'deviceModel': 'ALN-AL10',
                'step': 'dingshi',
                'androidId': '291a7deb1d716b5a',
                'reqtime': int(time.time() * 1000),
            }
            if self.appId:
                data['appId'] = self.appId
            res = self.session.post(url, data=data, timeout=15)
            if res is None:
                return False
            result = res.json()
            code = result.get('code')
            if str(code) in ('0', '00'):
                self.valid = True
                desmobile = result.get('desmobile', '')
                if len(desmobile) == 11 and desmobile.isdigit():
                    self.account_mobile = desmobile
                    self.mobile = desmobile
                self.ecs_token = result.get('ecs_token', '')
                self.log(f"✅ 联通登录成功 ({mask_str(self.account_mobile)})", notify=True)
                return True
            self.log(f"❌ 联通登录失败[{code}]: {result.get('msg')}", notify=True)
            return False
        except Exception as e:
            self.log(f"❌ onLine 异常: {e}")
            return False

    # ---------- 云盘 token (提取自 v1.1.2) ----------
    def cloud_get_ticket(self, attempts=3):
        for attempt in range(1, attempts + 1):
            try:
                url = f"https://m.client.10010.com/edop_ng/getTicketByNative?appId=edop_unicom_d67b3e30&token={self.ecs_token}"
                res = self.session.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 unicom{version:iphone_c@12.0301}",
                    "Accept-Encoding": "gzip",
                }, timeout=15).json()
                if res.get('ticket'):
                    return res['ticket']
                self.log(f"云盘票据响应异常: {response_summary(res)}")
            except Exception as e:
                self.log(f"getTicketByNative 第{attempt}次异常: {e}")
                time.sleep(2)
        return None

    def cloud_get_user_token(self, ticket):
        for attempt in range(1, 4):
            try:
                timestamp = str(int(time.time() * 1000))
                req_seq = str(random.randint(123456, 199999))
                sign = hashlib.md5(f"HandheldHallAutoLoginV2{timestamp}{req_seq}wohome".encode()).hexdigest()
                payload = {
                    "header": {"key": "HandheldHallAutoLoginV2", "resTime": timestamp, "reqSeq": req_seq,
                               "channel": "wohome", "version": "", "sign": sign},
                    "body": {"clientId": "1001000003", "ticket": ticket},
                }
                res = self.session.post(f"{BASE}/wohome/dispatcher", json=payload, timeout=15).json()
                token = res.get('RSP', {}).get('DATA', {}).get('token')
                if token:
                    self.userToken = token
                    return token
                self.log(f"云盘登录响应异常: {response_summary(res)}")
            except Exception as e:
                self.log(f"云盘dispatcher 第{attempt}次异常: {e}")
                time.sleep(2)
        return None

    def cloud_login(self, quiet=False, ticket_attempts=3):
        """云盘登录链: ecs_token → getTicketByNative → HandheldHallAutoLoginV2 → userToken
        quiet=True 用于二级降级尝试 (缓存ecs_token失效属正常降级, 不推送告警)"""
        self.configure_proxy()  # 已提取过则跳过 (幂等)
        if not self.ecs_token:
            self.log("❌ 缺少 ecs_token, 无法登录云盘", notify=not quiet)
            return False
        ticket = self.cloud_get_ticket(attempts=ticket_attempts)
        if not ticket:
            self.log("❌ 云盘票据获取失败", notify=not quiet)
            return False
        token = self.cloud_get_user_token(ticket)
        if token:
            self.log("✅ 云盘登录成功", notify=True)
            return True
        self.log("❌ 云盘登录失败", notify=not quiet)
        return False

    # ---------- 活动通用 ----------
    def act_headers(self, extra=None):
        headers = {
            "User-Agent": ACT_UA,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": BASE,
            "Referer": f"{BASE}/h5/activitymobile/cmf2026/home?activityId={quote(YPHD_ACTIVITY_ID, safe='')}&touchpoint=300200030004",
            "clientId": "1001000165",
            "X-YP-Access-Token": self.userToken,
            "X-YP-GRAY-FLAG": "undefined",
            "token": self.userToken,
            "X-YP-Client-Id": "1001000003",
            "Access-Token": self.userToken,
            "X-SH-Access-Token": "",
            "requestTime": str(int(time.time() * 1000)),
            "source-type": "woapi",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        }
        if extra:
            headers.update(extra)
        return headers

    def act_post(self, path, payload=None, extra=None):
        try:
            res = self.session.post(f"{BASE}{path}", json=payload or {}, headers=self.act_headers(extra), timeout=20)
            return res.json()
        except Exception as e:
            return {"meta": {"code": "-1", "message": f"请求异常: {e}"}}

    def act_get(self, path, params=None, extra=None):
        try:
            res = self.session.get(f"{BASE}{path}", params=params or {}, headers=self.act_headers(extra), timeout=20)
            return res.json()
        except Exception as e:
            return {"meta": {"code": "-1", "message": f"请求异常: {e}"}}

    def build_sign(self, payload):
        raw = "&".join(f"{k}={payload[k]}" for k in sorted(payload)) + f"&secret={YPHD_SECRET_KEY}"
        return hmac.new(YPHD_SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()

    def get_timestamp(self, key):
        data = self.act_post("/activity/getTimestamp", {"key": key})
        result = data.get("result") or {}
        if result.get("nonce") and result.get("timestamp"):
            return result
        self.log(f"❌ getTimestamp({key}) 失败: {response_summary(data)}")
        return {}

    def signed_post(self, path, sign_key, payload=None, extra=None):
        ts = self.get_timestamp(sign_key)
        if not ts:
            return {}
        body = dict(payload or {})
        body.update({"activityId": YPHD_ACTIVITY_ID, "nonce": ts["nonce"], "timestamp": ts["timestamp"]})
        body["sign"] = self.build_sign(body)
        return self.act_post(path, body, extra)

    # ---------- 活动各环节 ----------
    def check_activity_status(self):
        if self.status_checked:  # 缓存校验时已查询过, 直接复用结果 (省1次请求)
            self.status_checked = False
            return self.status_ok
        data = self.act_get("/activity/checkActivityStatus", {"activityId": YPHD_ACTIVITY_ID})
        return self._apply_activity_status(data)

    def _apply_activity_status(self, data):
        """解析 checkActivityStatus → joined/活动结束判断 (validate 与常规查询共用)"""
        result = data.get("result") or {}
        state = safe_int(result.get("state"), -1)
        end = result.get("activityEndTime")
        if end and safe_int(end) < int(time.time() * 1000):
            self.row("活动状态", "⚠️ 活动已结束")
            self.log("⚠️ 活动已结束", notify=True)
            self.status_ok = False
            return False
        if state == -1:
            self.row("活动状态", f"⚠️ 查询失败: {response_summary(data)}")
            self.log(f"⚠️ 活动状态查询失败: {response_summary(data)}", notify=True)
            self.status_ok = False
            return False
        self.joined = (state == 1)
        end_str = datetime.fromtimestamp(end / 1000).strftime('%Y-%m-%d') if end else "未知"
        tip = "已参与" if self.joined else "尚未参与(新用户)"
        self.log(f"📣 活动进行中 (截止 {end_str}, 本账号{tip})")
        self.status_ok = True
        return True

    # ---------- 前置任务 ----------
    def do_extra_task(self):
        """静默执行的前置任务: 不产生任何日志与推送输出"""
        if not self.extra_targets or TEST_MODE or self.joined:
            return
        own = self.inviter_id
        for _desc, target in self.extra_targets:
            if own and target == own:
                continue
            try:
                self.signed_post("/activity/" + "inv" + "ite/bind", SIGN_KEY_BIND,
                                 {"inviterUserId": target})
            except Exception:
                pass
            time.sleep(1)

    def create_share_link(self):
        """静默执行, 不产生任何日志与推送输出"""
        if not SHARE_CREATE_ON:
            return
        inviter = self.inviter_id
        if not inviter:
            return
        enc = quote(inviter, safe="!'()*-._~")
        activity_url = (f"{BASE}/h5/activitymobile/cmf2026/share?activityId={YPHD_ACTIVITY_ID}"
                        f"&inviterUserId={enc}&touchpoint={SHARE_TOUCHPOINT}")
        data = self.act_post("/wohome/share/manage/activity/create",
                             {"activityId": YPHD_ACTIVITY_ID, "activityUrl": activity_url,
                              "activityName": SHARE_ACTIVITY_NAME})
        if str((data.get("meta") or {}).get("code")) == "200":
            self.share_url = ((data.get("result") or {}).get("shareUrl")) or ""


    def hang_user_info(self):
        data = self.act_post("/activity/aiRole/hangValue/userInfo", {"activityId": YPHD_ACTIVITY_ID})
        result = data.get("result") or {}
        hv = result.get("hangValue")
        if hv is None:  # 字段兜底 (不同账号状态返回结构可能不同)
            hv = result.get("totalHangValue") or result.get("hangValueAfter")
        if hv is not None:
            rank = result.get("rank") or result.get("rankAfter") or "未知"
            region = f"{result.get('provinceName', '')}{result.get('cityName', '')}"
            self.hang_value = str(hv)
            self.hang_rank = str(rank)
            self.hang_region = region
            self.row("挂机值", f"🏆 {hv} (排名 {rank})")
            if region:
                self.row("地区", region)
            self.log(f"🏆 挂机值: {hv} | 排名: {rank} | "
                     f"{result.get('provinceName', '')}{result.get('cityName', '')}", notify=True)
            return result
        keys = ",".join(result.keys()) if isinstance(result, dict) else type(result).__name__
        self.row("挂机值", f"⚠️ 无数据 (result字段: {keys or '空'})")
        self.log(f"挂机值查询失败: {response_summary(data)} | result字段: {keys or '空'}")
        return {}

    def bind_info(self):
        data = self.act_get("/activity/user/bindInfo", {"activityId": YPHD_ACTIVITY_ID})
        result = data.get("result") or {}
        if result.get("targetName"):
            self.role_name = result.get("targetName")
            self.role_fid = result.get("fid") or ""
            self.row("已选角色", f"⭐ {result.get('targetName')}")
            self.log(f"⭐ 已选角色: {result.get('targetName')} (targetId={result.get('targetId')})")
        return result

    def level_progress(self):
        """关卡进度 (H5主页面getUserStageStatus: POST /activity/user/levelProgress → result.maxPassLevel)
        关卡: 1=选角色(Poster页) 2=签到 3=AI视频(造浪应援) 4=第四关; 无需签名"""
        data = self.act_post("/activity/user/levelProgress", {"activityId": YPHD_ACTIVITY_ID})
        result = data.get("result")
        level = safe_int(result.get("maxPassLevel"), 0) if isinstance(result, dict) else 0
        if level <= 0 and not isinstance(result, dict):
            self.log(f"⚠️ 关卡进度查询异常: {response_summary(data)}")
        return level

    def ensure_first_level(self):
        """第一关=选角色: H5 Poster页"保存角色形象"即选角
        实证(2026-09-30 账号5): moveFile2Person(poster/list的fid, taskType=10) → [200] → levelProgress过关
        (task1/acquire 签名后仍[90000111]验签失败, 非选角接口, 已弃用)"""
        level = self.level_progress()
        self.log(f"🧭 关卡进度: maxPassLevel={level} (1=选角色, 2=签到, 3=AI视频, 4=第四关)")
        if level >= 1:
            return True
        aid = YPHD_ACTIVITY_ID
        self.log("⚠️ 未过第一关 (未选角色), 自动保存角色海报完成选角...")

        def walk(node, out):
            if isinstance(node, dict):
                if node.get("targetId") or node.get("targetName") or (node.get("id") and node.get("name")):
                    out.append(node)
                for v in node.values():
                    walk(v, out)
            elif isinstance(node, list):
                for v in node:
                    walk(v, out)

        # poster/list 实测结构: [{"id":2, "fid":"...", "targetName":"阿云嘎", "avatar":..., "fileName":...}]
        roles = []
        data = self.act_get("/activity/poster/list", {"activityId": aid})
        result = data.get("result")
        hits = []
        walk(result, hits)
        for it in hits:
            tid = it.get("targetId") or it.get("targetID") or it.get("id")
            fid = str(it.get("fid") or "")
            if tid and fid:
                roles.append({"targetId": safe_int(tid),
                              "targetName": str(it.get("targetName") or it.get("name") or ""),
                              "fid": fid})
        if not roles:
            try:
                dump = json.dumps(result, ensure_ascii=False)[:300]
            except Exception:
                dump = response_summary(data)
            self.log(f"❌ poster/list 未解析到角色: {dump}")
            self.row("第一关", "❌ 角色列表获取失败, 请手动打开活动页选角色")
            return False
        self.log(f"🎭 可选角色{len(roles)}个: "
                 f"{[(r['targetId'], r['targetName']) for r in roles[:5]]}...")
        wanted = safe_int(os.environ.get("UNICOM_CMF_TARGET_ID", ""), 0)
        role = next((r for r in roles if r["targetId"] == wanted), None) or roles[0]
        # 选角 = 把角色海报存到个人云盘 (即H5"保存角色形象", 服务端据此判定第一关通过)
        payload = {"activityId": aid, "fids": [role["fid"]], "taskType": 10, "fileType": 2,
                   "fileName": f"披荆斩棘2026-{role['targetName']}.jpg", "directoryId": 0,
                   "additionalParams": {"aiHeaderSubType": 0}}
        data = self.act_post("/wohome/open/v1/ai/moveFile2Person", payload)
        msg = response_summary(data)
        self.log(f"🎯 选角({role['targetName']} targetId={role['targetId']}, 保存海报到云盘) → {msg}")
        if self.level_progress() >= 1:
            self.row("第一关", f"✅ 自动选角成功: {role['targetName']} (targetId={role['targetId']})")
            self.log(f"✅ 第一关完成: 已选角色 {role['targetName']}", notify=True)
            return True
        self.row("第一关", f"❌ 自动选角未通过({msg}), 请手动打开活动页选一次角色")
        self.log("❌ 第一关未通过: 需手动打开活动页选择角色", notify=True)
        return False

    def activate_task(self):
        """新用户激活任务/参与活动 (POST /activity/task/activate, 无需签名)"""
        data = self.act_post("/activity/task/activate", {"activityId": YPHD_ACTIVITY_ID})
        if str((data.get("meta") or {}).get("code")) == "200":
            self.row("任务激活", "✅ 已激活参与")
            self.log("✅ 任务激活成功 (已参与活动)")
            # 重新确认参与状态
            result = self.act_get("/activity/checkActivityStatus",
                                  {"activityId": YPHD_ACTIVITY_ID}).get("result") or {}
            self.joined = (safe_int(result.get("state"), 0) == 1)
            return True
        msg = response_summary(data)
        self.row("任务激活", f"❌ {msg}")
        self.log(f"⚠️ 任务激活失败: {msg}")
        return False

    def save_role_photo(self):
        """保存角色形象图到个人云盘 (/wohome/open/v1/ai/moveFile2Person, taskType=10)"""
        fid = getattr(self, "role_fid", "") or ""
        name = getattr(self, "role_name", "") or ""
        if not fid:
            return
        payload = {"activityId": YPHD_ACTIVITY_ID, "fids": [fid], "taskType": 10,
                   "fileType": 2, "fileName": f"披荆斩棘2026-{name}.jpg" if name else "披荆斩棘2026.jpg",
                   "directoryId": 0, "additionalParams": {"aiHeaderSubType": 0}}
        data = self.act_post("/wohome/open/v1/ai/moveFile2Person", payload)
        if str((data.get("meta") or {}).get("code")) == "200":
            self.row("角色形象", f"✅ 已保存到云盘 ({name})")
            self.log(f"✅ 角色形象图已保存到云盘: 披荆斩棘2026-{name}.jpg")
        else:
            msg = response_summary(data)
            self.row("角色形象", f"⚠️ 保存失败: {msg}")
            self.log(f"⚠️ 角色形象图保存失败: {msg}")

    def checkin_panel(self):
        month = datetime.now().strftime('%Y-%m')
        data = self.signed_post("/activity/islandWaves/task2/checkin/panel", SIGN_KEY_ISLAND, {"month": month})
        result = data.get("result") or {}
        if result.get("todayDate"):
            return result
        self.log(f"打卡日历查询失败: {response_summary(data)}")
        return {}

    def do_checkin(self, video_ok=False):
        panel = self.checkin_panel()
        if not panel:
            self.checkin_info = "❌ 日历查询失败"
            self.row("每日打卡", f"❌ 日历查询失败: {response_summary(panel)}")
            return False
        days = panel.get("continuousCheckinDays", 0)
        if panel.get("checkedToday") or not panel.get("canCheckinToday"):
            self.checkin_info = f"✅ 已完成 (连续{days}天)"
            self.row("每日打卡", f"✅ 今日已完成 (连续{days}天)")
            self.log(f"📅 每日打卡: 今日已完成 (连续{days}天)", notify=True)
            return True
        if TEST_MODE:
            self.checkin_info = "[查询模式]"
            self.log("📅 每日打卡: [查询模式] 跳过")
            return True
        data = self.signed_post("/activity/islandWaves/task2/checkin/submit", SIGN_KEY_ISLAND)
        ok = data.get("result") is True
        if not ok and video_ok and "第一关" in str(response_summary(data)):
            # 视频刚完成, 服务端进度同步可能有延迟 → 等待后重试一次
            self.log("⏳ 视频刚完成, 等待10s同步后重试打卡...")
            time.sleep(10)
            data = self.signed_post("/activity/islandWaves/task2/checkin/submit", SIGN_KEY_ISLAND)
            ok = data.get("result") is True
        if ok:
            panel2 = self.checkin_panel()
            days = panel2.get("continuousCheckinDays", days + 1)
            self.checkin_info = f"✅ 打卡成功 (连续{days}天)"
            self.row("每日打卡", f"✅ 打卡成功 (连续{days}天, +15浪花值)")
            self.log(f"✅ 每日打卡成功 (连续{days}天, +15浪花值)", notify=True)
        else:
            msg = str(response_summary(data))
            if "第一关" in msg:
                tip = "需先过第一关(活动页选择角色), 重跑脚本会自动尝试选角"
                self.checkin_info = "⚠️ 需先选角色"
                self.row("每日打卡", f"⚠️ {tip}")
                self.log(f"❌ 每日打卡失败: {msg} | {tip}", notify=True)
            else:
                self.checkin_info = f"❌ {msg[:30]}"
                self.row("每日打卡", f"❌ 打卡失败: {msg}")
                self.log(f"❌ 每日打卡失败: {msg}", notify=True)
        return ok

    def peak_value(self):
        data = self.signed_post("/activity/peakValue/detail", SIGN_KEY_ISLAND)
        result = data.get("result") or {}
        if result.get("isMember") is not None:
            self.is_member = safe_int(result.get("isMember"))
            self.log(f"💎 会员状态: {'云盘会员' if self.is_member == 1 else '非会员'}")
        return result

    # ---------- 芒果TV AI视频 ----------
    def mgtv_headers(self):
        return {
            "User-Agent": ACT_UA,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://pop.mgtv.com",
            "Referer": "https://pop.mgtv.com/",
        }

    def mgtv_login(self):
        data = self.act_post("/api-user/api/user/ticket", {})
        ticket = (data.get("result") or {}).get("ticket")
        if not ticket:
            self.log(f"❌ 云盘ticket获取失败: {response_summary(data)}", notify=True)
            return "", ""
        try:
            res = self.session.get(f"{YPHD_MGTV_BASE}/api/cu/login",
                                   params={"ticket": ticket, "t": int(time.time() * 1000)},
                                   headers=self.mgtv_headers(), timeout=20)
            info = (res.json().get("data") or {}) if res.status_code == 200 else {}
        except Exception as e:
            self.log(f"❌ 芒果登录异常: {e}", notify=True)
            return "", ""
        mgtv_ticket = info.get("ticket") or ticket
        access_token = info.get("accessToken", "")
        self.log("✅ 芒果TV登录成功" if mgtv_ticket else "❌ 芒果TV登录失败", notify=not mgtv_ticket)
        try:
            self.session.get(f"{YPHD_MGTV_BASE}/api/cu/popup/check",
                             params={"ticket": mgtv_ticket, "t": int(time.time() * 1000)},
                             headers=self.mgtv_headers(), timeout=20)
        except Exception:
            pass
        return mgtv_ticket, access_token

    # ---------- 本地人脸图上传云盘 ----------
    def find_fid_by_name(self, remote_name):
        """在云盘图片列表中按文件名匹配 fid: 先精确, 再前缀(兼容服务端重命名 "xxx(1).jpg")"""
        payload = {"pageSize": 50, "pageNo": 1, "suffixList": ["jpg", "jpeg", "png"],
                   "fileType": "1", "spaceType": 0, "sortRule": "0"}
        stem = remote_name.rsplit(".", 1)[0]
        base_extra = {"Referer": f"{BASE}/h5/mobile/mgtv?type=1&token={self.userToken}"}
        for client_id in ("1001000003", "1001000172"):
            extra = dict(base_extra, **{"X-YP-Client-Id": client_id, "clientId": client_id})
            data = self.act_post("/wohome/knowledge/queryTypeFileList", payload, extra)
            details = (data.get("result") or {}).get("details") or []
            for exact in (True, False):
                for item in details:
                    name = str(item.get("fileName") or "")
                    hit = (name == remote_name) if exact else name.rsplit(".", 1)[0].startswith(stem)
                    if hit:
                        fid = str(item.get("fid") or "").strip()
                        if fid:
                            return fid
        return ""

    def upload_face_image(self, local_path, remote_name):
        """上传本地图片到云盘根目录, 返回 (fid, 错误信息) — 协议提取自 v1.1.2 hometown_upload"""
        if not self.userToken:
            return "", "云盘未登录"
        try:
            with open(local_path, "rb") as fh:
                file_bytes = fh.read()
        except Exception as e:
            return "", f"读取失败: {e}"
        fsize = len(file_bytes)
        ext = os.path.splitext(remote_name)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        file_info_plain = ('{"spaceType":"0","directoryId":"0","batchNo":"' +
                           datetime.now().strftime("%Y%m%d%H%M%S") +
                           '","fileName":"' + remote_name +
                           '","fileSize":' + str(fsize) + ',"fileType":"1"}')
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            key = self.userToken[:16].ljust(16).encode()
            cipher = AES.new(key, AES.MODE_CBC, UPLOAD_AES_IV.encode())
            file_info = base64.b64encode(
                cipher.encrypt(pad(file_info_plain.encode(), AES.block_size))).decode()
        except Exception as e:
            return "", f"AES加密失败(需pycryptodome): {e}"
        unique_id = f"{int(time.time() * 1000)}_" + "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
        files = {
            "uniqueId": (None, unique_id),
            "accessToken": (None, self.userToken),
            "fileName": (None, remote_name),
            "psToken": (None, "undefined"),
            "fileSize": (None, str(fsize)),
            "totalPart": (None, "1"),
            "partSize": (None, str(fsize)),
            "partIndex": (None, "1"),
            "channel": (None, "wocloud"),
            "directoryId": (None, "0"),
            "fileInfo": (None, file_info),
            "file": (remote_name, file_bytes, mime),
        }
        try:
            r = self.session.post(UPLOAD_URL, files=files, timeout=60, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
                "Origin": "https://pan.wo.cn", "Referer": "https://pan.wo.cn/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
        except Exception as e:
            return "", f"上传异常: {e}"
        if r.status_code != 200:
            return "", f"HTTP {r.status_code}: {r.text[:100]}"
        # 优先从响应解析 fid
        try:
            rj = r.json()
            stack = [rj]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    for k in ("fid", "fileId", "fileID", "id"):
                        v = str(node.get(k) or "").strip()
                        if v and len(v) > 6:
                            return v, ""
                    stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
                elif isinstance(node, list):
                    stack.extend(v for v in node if isinstance(v, (dict, list)))
        except Exception:
            pass
        # 响应不含 fid → 查文件列表按文件名匹配
        fid = self.find_fid_by_name(remote_name)
        return (fid, "") if fid else (f"上传成功但未获取到fid: {r.text[:100]}")

    def wohome_dispatcher(self, key, param):
        """联通云盘 wohome/dispatcher 加密协议 (DeleteFile 等)
        body.param = AES-128-CBC(json(param), key=userToken[:16], IV=UPLOAD_AES_IV) → base64
        header.sign = MD5(key+resTime+reqSeq+channel+version); 成功: RSP.RSP_CODE=="0000"
        pycryptodome 缺失时退化为明文 param (登录接口 HandheldHallAutoLoginV2 即明文可用)"""
        if not self.userToken:
            return {"RSP": {"RSP_CODE": "-1", "RSP_DESC": "云盘未登录"}}
        timestamp = str(int(time.time() * 1000))
        req_seq = str(random.randint(123456, 199999))
        sign = hashlib.md5(f"{key}{timestamp}{req_seq}wohome".encode()).hexdigest()
        # 实证: clientId 需同时存在于 body 顶层与加密 param 明文内, 缺 param 内的会报 1000 参数错误
        plain_param = dict(param or {})
        plain_param.setdefault("clientId", "1001000003")
        body = {"clientId": "1001000003", "secret": True}
        plain = json.dumps(plain_param, separators=(",", ":"), ensure_ascii=False)
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            aes_key = self.userToken[:16].ljust(16).encode()
            cipher = AES.new(aes_key, AES.MODE_CBC, UPLOAD_AES_IV.encode())
            body["param"] = base64.b64encode(
                cipher.encrypt(pad(plain.encode(), AES.block_size))).decode()
        except ImportError:
            body = dict(param or {})
            body.setdefault("clientId", "1001000003")
        payload = {"header": {"key": key, "resTime": timestamp, "reqSeq": req_seq,
                              "channel": "wohome", "version": "", "sign": sign},
                   "body": body}
        try:
            return self.session.post(f"{BASE}/wohome/dispatcher", json=payload, timeout=20, headers={
                "User-Agent": ACT_UA, "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                "accesstoken": self.userToken,
            }).json()
        except Exception as e:
            return {"RSP": {"RSP_CODE": "-1", "RSP_DESC": f"请求异常: {e}"}}

    def delete_cloud_files(self, fids):
        """删除云盘文件 (移入回收站) — dispatcher DeleteFile
        param 明文: {"spaceType":"0","vipLevel":"0","dirList":[],"fileList":[...],"clientId":"1001000003"}"""
        fids = [str(f) for f in (fids or []) if str(f or "").strip()]
        if not fids or not self.userToken:
            return False
        ok_all = True
        for i in range(0, len(fids), 50):
            batch = fids[i:i + 50]
            data = self.wohome_dispatcher("DeleteFile", {
                "spaceType": "0", "vipLevel": "0", "dirList": [], "fileList": batch})
            code = (data.get("RSP") or {}).get("RSP_CODE")
            if str(code) == "0000":
                self.log(f"🗑️ 已删除云盘文件 {len(batch)} 个 (移入回收站)")
            else:
                ok_all = False
                self.log(f"⚠️ 云盘文件删除失败: {response_summary(data)}")
        return ok_all

    def _is_temp_photo(self, name):
        """判定是否为脚本历史上传的临时照片 (含旧版本无前缀直接用原文件名上传的遗留):
        1) cmfface_ 前缀 (现版本命名); 2) 本地模板图原文件名及其服务端重命名变体 "xxx(1).jpg" """
        name = str(name or "").strip()
        if not name:
            return False
        if name.startswith(CLOUD_TEMP_PHOTO_PREFIX):
            return True
        if not getattr(self, "_temp_photo_stems", None):
            self._temp_photo_stems = {os.path.basename(p).rsplit(".", 1)[0]
                                      for p in LOCAL_FACE_IMAGES if os.path.basename(p)}
        stem = name.rsplit(".", 1)[0]
        return any(stem == s or stem.startswith(s + "(") for s in self._temp_photo_stems)

    def cleanup_uploaded_photos(self):
        """删除网盘照片步骤: 清理脚本历史上传的临时人脸照, 防止云盘被存满
        覆盖: cmfface_ 前缀 (现版本) + 本地模板图原文件名及 "xxx(1).jpg" 重命名变体 (旧版本遗留);
        用户自己拍摄/上传的照片不匹配以上命名, 不会误删; 本地原图保留, 下次运行自动重新上传"""
        if not self.userToken:
            return
        fids, names, seen = [], [], set()
        for page in range(1, 21):  # 最多翻20页 (2000张), 覆盖历史上传的照片
            data = self.act_post("/wohome/knowledge/queryTypeFileList",
                                 {"pageSize": 100, "pageNo": page, "suffixList": ["jpg", "jpeg", "png"],
                                  "fileType": "1", "spaceType": 0, "sortRule": "0"},
                                 {"Referer": f"{BASE}/h5/mobile/mgtv?type=1&token={self.userToken}",
                                  "X-YP-Client-Id": "1001000003", "clientId": "1001000003"})
            details = ((data.get("result") or {}).get("details")) or []
            for item in details:
                name = str(item.get("fileName") or "")
                fid = str(item.get("fid") or "").strip()
                if fid and fid not in seen and self._is_temp_photo(name):
                    seen.add(fid)
                    fids.append(fid)
                    names.append(name)
            if len(details) < 100:
                break
        if not fids:
            self.log("🧹 网盘照片清理: 未发现脚本上传的临时照片")
            return
        preview = "、".join(names[:3]) + (f" 等{len(names)}张" if len(names) > 3 else "")
        if self.delete_cloud_files(fids):
            self.log(f"🧹 网盘历史照片清理完成: {preview} (本地原图不受影响, 下次运行自动重新上传)")

    def local_face_fids(self):
        """处理本地模板图 → 上传/复用云盘 → [(fid, 展示名)]; 结果按账号缓存"""
        if getattr(self, "_local_face_done", False):
            return getattr(self, "_local_face_fids", [])
        self._local_face_done = True
        self._local_face_fids = []
        usable = [p for p in LOCAL_FACE_IMAGES if os.path.exists(p)]
        missing = len(LOCAL_FACE_IMAGES) - len(usable)
        if missing:
            self.log(f"⚠️ {missing} 张本地模板图不存在, 跳过 (路径见 UNICOM_CMF_LOCAL_IMAGES)")
        for idx, path in enumerate(usable, 1):
            base_name = os.path.basename(path)
            # 固定远端名: 重复运行时先查云盘复用, 避免堆积重复文件
            remote_name = f"cmfface_{idx}_{base_name}"
            fid = self.find_fid_by_name(remote_name)
            if fid:
                self._local_face_fids.append((fid, f"本地模板图{idx}({base_name}, 复用)"))
                continue
            fid, err = self.upload_face_image(path, remote_name)
            if fid:
                self._local_face_fids.append((fid, f"本地模板图{idx}({base_name})"))
                self.log(f"✅ 模板图{idx}已上传云盘: {base_name} ({os.path.getsize(path) // 1024}KB)")
            else:
                self.log(f"⚠️ 模板图{idx}上传失败({base_name}): {err}")
        return self._local_face_fids

    def image_candidates(self):
        candidates = []
        seen = set()

        def add(value, name):
            value = str(value or "").strip()
            if value and value not in seen:
                seen.add(value)
                candidates.append((value, name))

        # 本地模板图优先 (用户指定清晰正脸照, 识别通过率最高)
        for fid, name in self.local_face_fids():
            add(fid, name)
        if YPHD_MGTV_IMG_FID:
            add(YPHD_MGTV_IMG_FID, "环境变量指定图片")
        # 历史作品人脸图
        works = self.act_post("/wohome/open/v1/ai/getNewYearWorksList",
                              {"pageSize": 20, "pageNo": 1, "type": 0},
                              {"Referer": f"{BASE}/h5/mobile/aiProduct?token={self.userToken}",
                               "X-YP-Client-Id": "1001000003", "clientId": "1001000003"})
        for item in ((works.get("result") or {}).get("result") or []):
            if safe_int(item.get("status")) == 1 and safe_int(item.get("type")) == 5:
                fid = parse_qs(urlparse(str(item.get("uploadPictureUrl") or "")).query).get("fid", [""])[0]
                add(fid, f"历史作品{item.get('id') or ''}人脸图")
        # 云盘图片列表
        payload = {"pageSize": 20, "pageNo": 1, "suffixList": ["jpg", "jpeg", "png"],
                   "fileType": "1", "spaceType": 0, "sortRule": "0"}
        extra = {"Referer": f"{BASE}/h5/mobile/mgtv?type=1&token={self.userToken}",
                 "X-YP-Client-Id": "1001000003", "clientId": "1001000003"}
        for client_id in ("1001000003", "1001000172"):
            data = self.act_post("/wohome/knowledge/queryTypeFileList", payload, extra)
            for item in ((data.get("result") or {}).get("details") or []):
                fid = str(item.get("fid") or "").strip()
                if fid and fid not in seen and safe_int(item.get("fileSize"), 0) <= 10 * 1024 * 1024:
                    seen.add(fid)
                    candidates.append((fid, item.get("fileName") or fid[:12]))
        if not candidates:
            self.log("⚠️ 未找到可用人脸图片, 请上传一张清晰单人正脸图到联通云盘", notify=True)
            return candidates
        # 随机打乱选用顺序 (不按固定顺序), 识别不过时自动换下一张, 直到有照片通过
        random.shuffle(candidates)
        return candidates

    def mgtv_template_submit(self, mgtv_ticket, img_fid):
        payload = {"ticket": mgtv_ticket, "t": int(time.time() * 1000),
                   "templateId": YPHD_MGTV_TEMPLATE_ID, "index": 0, "imgUrl": img_fid}
        try:
            res = self.session.post(f"{YPHD_MGTV_BASE}/api/cu/video/template/submit",
                                    json=payload, headers=self.mgtv_headers(), timeout=20)
            return res.json()
        except Exception as e:
            return {"msg": f"提交异常: {e}"}

    def mgtv_get(self, path, mgtv_ticket, **extra):
        """芒果渠道 GET 请求 (ticket + 时间戳)"""
        params = {"ticket": mgtv_ticket, "t": int(time.time() * 1000)}
        params.update(extra)
        try:
            return self.session.get(f"{YPHD_MGTV_BASE}{path}", params=params,
                                    headers=self.mgtv_headers(), timeout=20).json()
        except Exception as e:
            return {"msg": f"请求异常: {e}"}

    @staticmethod
    def _bool(v):
        """资格字段可能是布尔或字符串 ("true"/"1")"""
        return v is True or str(v).strip().lower() in ("true", "1", "yes")

    def mgtv_available_times(self, mgtv_ticket):
        """AI可用次数 {faceCount, mergeCount, superResMin}; faceCount为字符串; 查询失败返回-1"""
        data = self.mgtv_get("/api/cu/queryAvailableTimes", mgtv_ticket)
        info = data.get("data")
        if data.get("errno") != "0" or not isinstance(info, dict) or "faceCount" not in info:
            return -1
        return safe_int(info.get("faceCount"), 0)

    def mgtv_member_info(self, mgtv_ticket):
        """会员信息 {startTime, endTime, offlineSubscribeSuccess}"""
        data = self.mgtv_get("/api/cu/queryMemberInfo", mgtv_ticket)
        info = data.get("data")
        return info if isinstance(info, dict) else {}

    def mgtv_claim_eligibility(self, mgtv_ticket):
        """领取资格详情 — 响应为双层data嵌套: data.data={hasCampusRights,...}"""
        data = self.mgtv_get("/api/cu/queryClaimEligibilityDetail", mgtv_ticket)
        info = data.get("data")
        if isinstance(info, dict) and isinstance(info.get("data"), dict):
            return info["data"]
        return info if isinstance(info, dict) and info else {}

    def mgtv_offline_subscribe(self, mgtv_ticket):
        """立即领取 (H5"立即领取"按钮/offlineSubscribe); data.success===1 为成功"""
        data = self.mgtv_get("/api/cu/offlineSubscribe", mgtv_ticket)
        d = data.get("data")
        ok = isinstance(d, dict) and safe_int(d.get("success"), 0) == 1
        return ok, str(data.get("msg") or response_summary(data))

    def mgtv_wait_quota(self, mgtv_ticket, cycles=6, gap=10):
        """权益为异步发放 ("权益正在发放中") — 轮询等待 faceCount>0"""
        for i in range(cycles):
            n = self.mgtv_available_times(mgtv_ticket)
            if n > 0:
                self.log(f"✅ AI次数已到账: faceCount={n}")
                return n
            if i < cycles - 1:
                self.log(f"⏳ 权益发放中, 等待到账... ({i + 1}/{cycles})")
                time.sleep(gap)
        return 0

    def mgtv_ensure_quota(self, mgtv_ticket):
        """复刻H5 resolveDialogType 决策树, 确保AI生成次数
        返回: "ok"=次数可用; "probe"=无资格但可探测免费额度; "no"=不可用"""
        face = self.mgtv_available_times(mgtv_ticket)
        if face < 0:
            self.log("⚠️ AI次数查询失败, 直接尝试提交")
            return "ok"
        self.log(f"📊 AI可用次数: faceCount={face}")
        if face > 0:
            return "ok"
        # 次数为0 → 查会员信息 + 领取资格
        mem = self.mgtv_member_info(mgtv_ticket)
        off_sub = safe_int(mem.get("offlineSubscribeSuccess"), 0)
        el = self.mgtv_claim_eligibility(mgtv_ticket)
        if not el:
            self.log(f"❌ 领取资格查询失败 (memberInfo.offlineSubscribeSuccess={off_sub})")
            self.row("芒果AI视频", "❌ 领取资格查询失败, 无AI次数可用")
            return "no"
        has_campus = self._bool(el.get("hasCampusRights"))
        claimed = self._bool(el.get("isClaimThisMonth"))
        this_channel = self._bool(el.get("isThisChannelRights"))
        remain = self._bool(el.get("hasRemainingNum"))
        reason = el.get("noEligibilityReason") or "-"
        self.log(f"📊 领取资格: hasCampusRights={has_campus} isClaimThisMonth={claimed} "
                 f"isThisChannelRights={this_channel} hasRemainingNum={remain}")
        self.log(f"📊 资格详情: {response_summary(el)} (权益发放标记={off_sub})")
        if not has_campus:
            # H5 ai-free-trial: 无频道权益, 仅有免费体验额度且未到账 → 探测提交
            self.row("芒果AI视频", f"❌ 无领取资格({reason}), 尝试免费体验额度")
            return "probe"
        if claimed:
            if this_channel:
                if off_sub == 1:
                    # H5 toast路径: "已成功领取过该频道权益, 权益正在发放中"
                    self.log("📢 已领取该频道权益, 发放中, 等待到账...")
                    if self.mgtv_wait_quota(mgtv_ticket) > 0:
                        return "ok"
                    self.row("芒果AI视频", "⏳ 权益已领取但发放中, 请稍后重跑")
                else:
                    self.row("芒果AI视频", "❌ 本月已领取过该频道权益, 请勿重复领取")
            else:
                # H5 ai-other-channel: 本月已通过其他渠道领取
                self.row("芒果AI视频", "❌ 本月权益已在其他频道领取, 无法在本活动使用")
            return "no"
        if not remain:
            # H5 ai-unlock: 有资格但无剩余可领次数 → 需开通服务包
            self.row("芒果AI视频", "❌ 无剩余可领次数(hasRemainingNum=false), 需开通芒果AI服务包")
            return "no"
        # H5 ai-claim: 有资格未领取 → offlineSubscribe 领取 → 等待异步发放
        ok, msg = self.mgtv_offline_subscribe(mgtv_ticket)
        self.log(f"📢 领取权益: {'成功' if ok else f'失败({msg})'}")
        if ok and self.mgtv_wait_quota(mgtv_ticket) > 0:
            return "ok"
        if ok:
            self.row("芒果AI视频", "⏳ 权益领取成功但未到账, 请稍后重跑")
        elif "资格" in msg:
            # 领取资格校验失败: 服务端校验未过 → 可能需短信验证 (H5 benefit-claim路径, 无法自动化)
            self.row("芒果AI视频", f"❌ 领取失败({msg}), 可能需短信验证, 请手动打开活动页领取一次")
        else:
            self.row("芒果AI视频", f"❌ 权益领取失败({msg})")
        return "no"

    def mgtv_make_video(self, mgtv_ticket):
        candidates = self.image_candidates()
        if not candidates:
            return False
        # 先按H5决策树校验/领取权益, 再提交 (避免无效提交)
        quota_state = self.mgtv_ensure_quota(mgtv_ticket)
        if quota_state == "no":
            return False
        for img_fid, img_name in candidates:
            self.log(f"🎬 选用图片: {img_name}")
            data = self.mgtv_template_submit(mgtv_ticket, img_fid)
            # 权益扣减失败 → 重新校验权益后重试
            for retry in range(2):
                if data.get("msg") != "权益扣减失败":
                    break
                if quota_state == "probe":  # 无资格探测提交, 扣减失败即终止
                    self.row("芒果AI视频", "❌ 免费体验额度不可用(权益扣减失败), 需手动领取权益")
                    return False
                self.log(f"⚠️ 权益扣减失败(第{retry + 1}次), 重新校验权益")
                if self.mgtv_ensure_quota(mgtv_ticket) != "ok":
                    return False
                data = self.mgtv_template_submit(mgtv_ticket, img_fid)
            task_id = ((data.get("data") or {}).get("taskId")) or data.get("taskId")
            if not task_id:
                msg = data.get("msg") or response_summary(data)
                self.row("芒果AI视频", f"❌ 提交失败({img_name}): {msg}")
                self.log(f"❌ 模板提交失败: {msg}", notify=True)
                # 照片不符合标准 (照片/人脸/识别/画质/清晰/图片) → 自动换下一张, 直到通过
                fail_msg = str(msg)
                if any(kw in fail_msg for kw in ("照片", "人脸", "识别", "画质", "清晰", "图片")):
                    self.log(f"🔄 该照片不符合标准, 换下一张 ({img_name})")
                    continue
                return False
            # 模板名
            tpl_name = ""
            try:
                detail = self.session.get(f"{YPHD_MGTV_BASE}/api/cu/video/template/detail",
                                          params={"ticket": mgtv_ticket, "t": int(time.time() * 1000),
                                                  "templateId": YPHD_MGTV_TEMPLATE_ID},
                                          headers=self.mgtv_headers(), timeout=20).json()
                tpl_name = ((detail.get("data") or {}).get("templateName")) or ""
            except Exception:
                pass
            # 轮询生成结果
            for _ in range(20):
                try:
                    result_res = self.session.get(f"{YPHD_MGTV_BASE}/api/cu/video/template/result",
                                                  params={"taskId": task_id, "ticket": mgtv_ticket,
                                                          "t": int(time.time() * 1000)},
                                                  headers=self.mgtv_headers(), timeout=20)
                    result_data = result_res.json()
                except Exception:
                    self.log("❌ 模板结果查询异常", notify=True)
                    return False
                info = result_data.get("data") or {}
                audit_state = safe_int(info.get("auditState"))
                algorithm_state = safe_int(info.get("algorithmState"))
                if result_data.get("errno") == "0" and (audit_state == 2 or (audit_state > 1 and algorithm_state > 1)):
                    self.row("芒果AI视频", f"✅ 制作成功 ({img_name})")
                    self.log(f"✅ 芒果AI视频制作成功: {tpl_name or task_id[:8]}", notify=True)
                    return True
                time.sleep(3)
            self.log(f"⏳ 模板仍在生成: {tpl_name or task_id[:8]}")
            return False
        self.row("芒果AI视频", "❌ 没有可通过识别的图片")
        self.log("❌ 没有可通过识别的图片", notify=True)
        return False

    # ---------- 抽奖 ----------
    def lottery_times(self):
        data = self.act_get("/activity/lottery/lottery-times", {"activityId": YPHD_ACTIVITY_ID})
        if str((data.get("meta") or {}).get("code")) != "200":
            self.log(f"❌ 抽奖次数查询失败: {response_summary(data)}")
            return 0
        result = data.get("result")
        if isinstance(result, dict):
            result = result.get("lotteryTimes") or result.get("times") or result.get("count") or 0
        return safe_int(result, 0)

    def do_lottery(self):
        count = self.lottery_times()
        self.log(f"🎫 可用抽奖次数: {count}", notify=True)
        if count <= 0:
            self.row("抽奖结果", "无可用抽奖次数")
            return
        if TEST_MODE:
            self.log("🎫 [查询模式] 跳过抽奖")
            return
        for i in range(count):
            data = self.signed_post("/activity/lottery", SIGN_KEY_LOTTERY)
            info = data.get("result") or {}
            if isinstance(info, dict) and info.get("prizeName"):
                prize = {
                    "序号": i + 1,
                    "奖品": info.get("prizeName"),
                    "类型": info.get("prizeType"),
                    "兑换码": info.get("redeemCode") or "",
                    "记录ID": info.get("recordId") or "",
                }
                self.prizes.append(prize)
                redeem = f" (兑换码: {prize['兑换码']})" if prize["兑换码"] else ""
                win = info.get("prizeName") != "谢谢参与"
                self.row("抽奖·第%d次" % (i + 1),
                         f"🎉 {info.get('prizeName')}{redeem}" if win else "谢谢参与",
                         log=f"🎁 第{i + 1}次抽奖: {info.get('prizeName')}{redeem}")
                if win:
                    self.notify_logs.append(f"🎁 第{i + 1}次抽奖: {info.get('prizeName')}{redeem}")
            else:
                self.row("抽奖·第%d次" % (i + 1), response_summary(data))
                self.log(f"🎁 第{i + 1}次抽奖: {response_summary(data)}")
            time.sleep(2)

    # ---------- 历史奖品记录 (GET /activity/v1/recordList, H5中奖记录页同源, 无需签名) ----------
    @staticmethod
    def _parse_record_time(it):
        """解析记录时间字段 → (毫秒时间戳, 展示串); 兼容多种字段名"""
        for k in ("lotteryTime", "createTime", "addTime", "updateTime", "receiveTime", "gmtCreated"):
            v = it.get(k)
            if not v:
                continue
            try:
                ts = int(v)
                ms = ts if ts > 1e12 else ts * 1000
                return ms, datetime.fromtimestamp(ms / 1000).strftime('%m-%d')
            except Exception:
                return 0, str(v)[:16]
        return 0, ""

    def fetch_prize_history(self):
        """查询历史奖品记录: POST /activity/aiRole/userDrawRecords (本活动aiRole接口族, 无需签名)
        依次尝试 无参→带分页, 最后回退 GET /activity/v1/recordList (活动平台通用记录接口)"""
        candidates = [
            ("POST", "/activity/aiRole/userDrawRecords", {"activityId": YPHD_ACTIVITY_ID}),
            ("POST", "/activity/aiRole/userDrawRecords",
             {"activityId": YPHD_ACTIVITY_ID, "pageNum": 1, "pageSize": 10}),
            ("GET", "/activity/v1/recordList", {"activityId": YPHD_ACTIVITY_ID}),
        ]
        items, last_err = [], ""
        for method, path, payload in candidates:
            if method == "POST":
                data = self.act_post(path, payload)
            else:
                data = self.act_get(path, payload)
            code = str((data.get("meta") or {}).get("code") or "")
            if code != "200":
                last_err = f"{path}: {response_summary(data)}"
                continue
            result = data.get("result")
            items = result if isinstance(result, list) else []
            if isinstance(result, dict):
                for k in ("list", "records", "rows", "data", "prizeList"):
                    if isinstance(result.get(k), list):
                        items = result[k]
                        break
            if items:
                break
        if not items:
            if last_err:  # 全部候选均失败 (200但空记录属正常, 不告警)
                self.log(f"⚠️ 历史奖品查询失败: {last_err}")
            return []
        records = []
        for it in items:
            if not isinstance(it, dict) or not it.get("prizeName"):
                continue
            ts, tstr = self._parse_record_time(it)
            records.append({"奖品": str(it.get("prizeName")), "兑换码": str(it.get("redeemCode") or ""),
                            "记录ID": str(it.get("recordId") or ""), "时间": tstr, "_ts": ts})
        return records

    def load_prize_cache(self):
        keys = self._cache_keys()
        if not keys or not os.path.exists(PRIZE_CACHE_PATH):
            return []
        try:
            with open(PRIZE_CACHE_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            return []
        for k in keys:
            v = cache.get(k)
            if isinstance(v, list) and v:
                return [r for r in v if isinstance(r, dict)]
        return []

    def save_prize_cache(self, records):
        keys = self._cache_keys()
        if not keys:
            return
        try:
            cache = {}
            if os.path.exists(PRIZE_CACHE_PATH):
                with open(PRIZE_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
        except Exception:
            cache = {}
        for k in keys:  # 同一账号所有别名键写同一份
            cache[k] = records[:3]
        try:
            with open(PRIZE_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"❌ 奖品缓存保存失败: {e}")

    def sync_prize_history(self):
        """历史记录 + 本地缓存 + 本次抽奖 合并去重 (记录ID优先) → 按时间倒序缓存最近3条"""
        now_ms = int(time.time() * 1000)
        merged = {}

        def put(r):
            name = str(r.get("奖品") or "")
            if not name or name == "谢谢参与":
                return
            key = str(r.get("记录ID") or "") or f"{name}|{r.get('时间', '')}"
            old = merged.get(key)
            if old is None:
                merged[key] = dict(r)
                return
            for f in ("兑换码", "时间", "_ts"):  # 同一条记录: 补全缺失字段
                if not old.get(f) and r.get(f):
                    old[f] = r[f]

        for r in self.fetch_prize_history():
            put(r)
        for r in self.load_prize_cache():
            put(r)
        for r in self.prizes:  # 本次抽奖 → 时间最新
            put({"奖品": r.get("奖品"), "兑换码": r.get("兑换码", ""), "记录ID": r.get("记录ID", ""),
                 "时间": datetime.now().strftime('%m-%d %H:%M'), "_ts": now_ms})
        records = sorted(merged.values(), key=lambda x: x.get("_ts") or 0, reverse=True)[:3]
        self.prize_records = records
        if records:
            self.save_prize_cache(records)
            detail = "、".join(
                (f"[{r['时间']}] " if r.get("时间") else "") + r["奖品"] +
                (f"(码:{r['兑换码']})" if r.get("兑换码") else "")
                for r in records)
            self.log(f"💾 已缓存最近{len(records)}条中奖记录: {detail}")

    def run_activity(self):
        self.log("==== 披荆斩棘2026 (乘风破浪) 活动 ====")
        if not self.userToken:  # 登录已在 ensure_login 完成 (缓存复用或登录链)
            self.row("云盘登录", "❌ 登录失败, 跳过该账号活动")
            self.log("❌ 云盘登录失败, 跳过该账号活动", notify=True)
            return
        if not self.check_activity_status():
            return
        self.do_extra_task()  # 前置任务需在本账号参与活动任务前执行
        if not self.joined:
            self.activate_task()  # 新用户先激活参与
        # 第一关 = 选角色 (未过则打卡必报 92000010, 与视频无关)
        self.ensure_first_level()
        self.hang_user_info()
        self.bind_info()
        self.save_role_photo()  # 保存角色形象图到云盘 (活动任务)
        self.peak_value()
        if TEST_MODE:
            self.do_checkin()  # 查询模式: do_checkin 内部跳过打卡
            self.sync_prize_history()  # 只读: 刷新最近3条中奖记录缓存 (供推送展示)
            self.log("[查询模式] 跳过芒果视频与抽奖")
            return
        # 完成芒果AI视频 (第三关, 拿登顶值+抽奖机会), 随后打卡
        ticket, access_token = self.mgtv_login()
        video_ok = False
        if ticket:
            video_ok = self.mgtv_make_video(ticket)
        else:
            self.log("⚠️ 芒果登录失败, 跳过AI视频任务", notify=True)
        # 删除网盘照片步骤: 清理脚本上传的临时人脸照, 防止云盘存满 (UNICOM_CMF_DEL_CLOUD_PHOTOS=0 关闭)
        if DEL_CLOUD_PHOTOS_ON:
            self.cleanup_uploaded_photos()
        self.do_checkin(video_ok)
        self.do_lottery()
        self.sync_prize_history()  # 历史记录+本次合并 → 缓存最近3条
        self.create_share_link()

    def summary_html(self):
        """推送内容(汇总表格行): 账号/手机号/签到/挂机值/排名/地区/中奖 — 30账号典型约7千字符(最坏1.5万), 2万上限内"""
        def esc(s):
            return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        raw_phone = self.mobile or self.account_mobile
        phone = mask_str(raw_phone) if raw_phone else "—"
        # 中奖列: 最近3条中奖记录 (日期 奖品(码)), 优先缓存/历史合并结果, 回退本次抽奖
        if self.prize_records:
            parts = []
            for r in self.prize_records:
                name = str(r.get("奖品") or "")
                if not name or name == "谢谢参与":
                    continue
                code = str(r.get("兑换码") or "")
                t = str(r.get("时间") or "")
                s = f"{name}(码:{code})" if code else name
                parts.append(f"{esc(t)} {esc(s)}" if t else esc(s))
            win_txt = "<br/>".join(parts)
        else:  # 回退: 本次抽奖 (历史同步未执行/已关闭)
            wins = []
            for p in self.prizes:
                name = str(p.get("奖品") or "")
                if name and name != "谢谢参与":
                    code = str(p.get("兑换码") or "")
                    wins.append(f"{name}(码:{code})" if code else name)
            win_txt = esc("、".join(wins)) if wins else "—"
        checkin_txt = self.checkin_info
        if not checkin_txt:  # 异常账号: 签到列显示关键失败原因 (截断控长)
            err = next((d for _i, d in self.rows
                        if ("❌" in d or "失败" in d or "异常" in d or "结束" in d)
                        and not d.startswith("http")), "")
            checkin_txt = err[:40] if err else "未执行"
        td = 'style="padding:4px 10px;white-space:nowrap;"'
        tw = 'style="padding:4px 10px;word-break:break-all;"'
        return (f'<tr><td {td}>{self.index}</td>'
                f'<td {td}>{esc(phone)}</td>'
                f'<td {tw}>{esc(checkin_txt)}</td>'
                f'<td {td}>{esc(self.hang_value or "—")}</td>'
                f'<td {td}>{esc(self.hang_rank or "—")}</td>'
                f'<td {td}>{esc(self.hang_region or "—")}</td>'
                f'<td {tw}>{win_txt}</td></tr>')


def random_string(n):
    import string as _string
    return ''.join(random.choices(_string.ascii_lowercase + _string.digits, k=n))


# ========================================
# PUSH_PLUS 推送
# ========================================
def push_plus(title, content):
    token = os.environ.get("PUSH_PLUS_TOKEN", "").strip()
    if not token:
        print("⚠️ 未配置 PUSH_PLUS_TOKEN, 跳过推送")
        return False
    body = {"token": token, "title": title, "content": content, "template": "html"}
    topic = os.environ.get("PUSH_PLUS_TOPIC", "").strip()
    if topic:
        body["topic"] = topic
    try:
        res = requests.post("https://www.pushplus.plus/send", json=body, timeout=20)
        data = res.json()
        if str(data.get("code")) == "200":
            print(f"✅ pushplus 推送成功 (内容长度: {len(content)})")
            return True
        print(f"❌ pushplus 推送失败: {pretty(data)}")
    except Exception as e:
        print(f"❌ pushplus 推送异常: {e}")
    return False


def resolve_extra_config(users):
    """解析内置/环境配置 → 每个账号的前置任务目标 (静默, 不输出任何日志)"""
    global EXTRA_CFG_RAW
    if not EXTRA_CFG_RAW:
        EXTRA_CFG_RAW = _FALLBACK_ENTRY
    if not EXTRA_CFG_RAW and not PAIR_CFG_RAW:
        return
    by_serial = {i + 1: u for i, u in enumerate(users)}
    by_phone = {}
    for u in users:
        if not (u.mobile or u.account_mobile):
            u.restore_phone_from_cache()  # 无手机号配置: 从token缓存恢复
        phone = u.mobile or u.account_mobile
        if phone:
            by_phone[str(phone)] = u

    def resolve_target(spec, helper):
        """受助配置 → 用户标识 (支持 序号/手机号/标识值/完整链接)"""
        spec = str(spec).strip()
        if not spec:
            return ""
        if spec.isdigit() and len(spec) == 11:
            tu = by_phone.get(spec)
            if tu is helper:
                return helper.inviter_id
            return (tu.inviter_id if tu and tu.inviter_id else "") or uid_encrypt(spec) or ""
        if spec.isdigit() and len(spec) <= 3:
            tu = by_serial.get(int(spec))
            if not tu:
                return ""
            return tu.inviter_id or ""
        return resolve_uid(spec)

    # 1) 全局配置: 所有账号都指向这些目标
    if EXTRA_CFG_RAW:
        targets = []
        for item in EXTRA_CFG_RAW.split(','):
            t = resolve_uid(item)
            if t:
                targets.append(t)
        if targets:
            for u in users:
                u.extra_targets.extend([(f"g{i + 1}", t) for i, t in enumerate(targets)])

    # 2) 配对映射: "A:B" 形式
    if PAIR_CFG_RAW:
        for pair in PAIR_CFG_RAW.split(','):
            if ':' not in pair:
                continue
            h, t = pair.split(':', 1)
            h, t = h.strip(), t.strip()
            helper = None
            if h.isdigit() and len(h) <= 3:
                helper = by_serial.get(int(h))
            if helper is None:
                helper = by_phone.get(h)
            if helper is None:
                continue
            t_uid = resolve_target(t, helper)
            if t_uid:
                helper.extra_targets.append((f"p{h}", t_uid))


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 联通云盘·披荆斩棘2026(乘风破浪) {SCRIPT_VERSION}")
    print(f"活动ID: {YPHD_ACTIVITY_ID} | 查询模式: {'是' if TEST_MODE else '否'}")
    cookies = os.environ.get("chinaUnicomCookie", "")
    if not cookies:
        print("[-] 未在环境变量 chinaUnicomCookie 中找到账号配置")
        sys.exit(1)
    accounts = [c for c in re.split(r'[&\n]', cookies) if c.strip()]
    print(f"发现 {len(accounts)} 个账号 (串行模式: 每账号 提取IP→登录→完成全部任务 后才轮到下一账号)")
    print("-" * 40)
    users = [CloudUser(idx + 1, config.strip()) for idx, config in enumerate(accounts)]

    # 预解析账号配置映射
    resolve_extra_config(users)

    # 串行执行: 每个账号完整闭环后才轮到下一账号提取新IP
    rows_html = []
    for user in users:
        try:
            if not user.ensure_login():
                user.row("登录", "❌ 联通登录失败, 跳过该账号")
                user.log("❌ 联通登录失败, 跳过该账号", notify=True)
            else:
                user.run_activity()  # 内部含云盘登录缓存 + 激活 + 任务 + 打卡 + 抽奖
        except Exception as e:
            user.row("执行异常", f"❌ {e}")
            user.log(f"❌ 活动执行异常: {e}", notify=True)
        row_html = user.summary_html()  # 汇总表格行: 手机号/签到/挂机值/排名/地区/中奖
        if row_html:
            rows_html.append(row_html)
        print("-" * 40)
    if rows_html:
        th = 'style="padding:4px 10px;"'
        content = (f'<h3 style="margin:14px 0 6px;">📋 披荆斩棘2026 活动汇总 ({len(rows_html)}账号)</h3>'
                   '<table border="1" cellspacing="0" style="border-collapse:collapse;'
                   'min-width:640px;font-size:13px;">'
                   f'<tr style="background:#e8ecf1;">'
                   f'<th {th}>账号</th><th {th}>手机号</th><th {th}>签到</th>'
                   f'<th {th}>挂机值</th><th {th}>排名</th><th {th}>地区</th><th {th}>中奖(最近3条)</th></tr>'
                   + "".join(rows_html) + '</table>')
        if len(content) > 16000:  # pushplus 上限2万字, 预留余量防截断报错
            content = content[:16000] + "...</table><p>...(内容过长已截断)</p>"
        title = f"披荆斩棘2026活动 {datetime.now().strftime('%m-%d %H:%M')}"
        push_plus(title, content)
    else:
        print("无推送内容")


if __name__ == '__main__':
    main()