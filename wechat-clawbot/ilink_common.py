#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信 ClawBot (iLink 协议) 公共底层库 (ilink_common.py)
提供：
- 标准请求头生成 (X-WECHAT-UIN, iLink-App-ClientVersion=132102, Bearer bot_token)
- HTTP POST / GET JSON 封装 (兼容 application/octet-stream 响应)
- OpenSSL AES-128-ECB (PKCS7 padding) 加解密与 CDN 媒体上传/下载
- 文本消息与图片/文件消息发送 (每次消耗 1 条 context_token 额度，单 token 上限 10 条)
"""

import os
import sys
import json
import time
import uuid
import base64
import struct
import hashlib
import urllib.request
import urllib.parse
import urllib.error
import subprocess

WECHAT_ROOT = "/workspace/files/wechat"
LIB_DIR = os.path.join(WECHAT_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"
CHANNEL_VERSION = "2.4.6"
CLIENT_VERSION = "132102"  # (2<<16)|(4<<8)|6 = 132102
BOT_AGENT = "TianjiBot/2.4.6 (python)"

def random_wechat_uin() -> str:
    val = struct.unpack(">I", os.urandom(4))[0]
    return base64.b64encode(str(val).encode("ascii")).decode("ascii")

def build_headers(bot_token: str = None, is_post: bool = True) -> dict:
    headers = {
        "iLink-App-Id": "bot",
        "iLink-App-ClientVersion": CLIENT_VERSION,
    }
    if is_post:
        headers["Content-Type"] = "application/json"
        headers["AuthorizationType"] = "ilink_bot_token"
        headers["X-WECHAT-UIN"] = random_wechat_uin()
    if bot_token:
        headers["Authorization"] = f"Bearer {bot_token}"
    return headers

def base_info() -> dict:
    return {
        "channel_version": CHANNEL_VERSION,
        "bot_agent": BOT_AGENT
    }

def http_post_json(url: str, payload: dict, bot_token: str = None, timeout: int = 15) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = build_headers(bot_token=bot_token, is_post=True)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}

def http_get_json(url: str, timeout: int = 38) -> dict:
    headers = build_headers(bot_token=None, is_post=False)
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}

def aes_128_ecb_encrypt(plaintext: bytes, key_bytes: bytes) -> bytes:
    key_hex = key_bytes.hex()
    p = subprocess.run(
        ["openssl", "enc", "-aes-128-ecb", "-K", key_hex],
        input=plaintext,
        capture_output=True,
        check=True
    )
    return p.stdout

def aes_128_ecb_decrypt(ciphertext: bytes, key_bytes: bytes) -> bytes:
    key_hex = key_bytes.hex()
    p = subprocess.run(
        ["openssl", "enc", "-d", "-aes-128-ecb", "-K", key_hex],
        input=ciphertext,
        capture_output=True,
        check=True
    )
    return p.stdout

def parse_aes_key(key_str: str) -> bytes:
    """
    支持三种格式：
    1. 32 位 hex 字符串 -> 16 bytes
    2. base64(16 bytes) -> 16 bytes
    3. base64(32 位 hex 字符串) -> 16 bytes
    """
    if not key_str:
        return b""
    s = key_str.strip()
    if len(s) == 32 and all(c in "0123456789abcdefABCDEF" for c in s):
        return bytes.fromhex(s)
    raw = base64.b64decode(s)
    if len(raw) == 16:
        return raw
    if len(raw) == 32:
        try:
            return bytes.fromhex(raw.decode("ascii"))
        except Exception:
            pass
    return raw[:16]

def load_bot_secret(bot_id: str) -> dict:
    secret_path = os.path.join(WECHAT_ROOT, "bots", bot_id, "secret.json")
    with open(secret_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_context_token(bot_id: str) -> str:
    tok_path = os.path.join(WECHAT_ROOT, "bots", bot_id, "context_token")
    if os.path.exists(tok_path):
        with open(tok_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def save_context_token(bot_id: str, token: str):
    if not token:
        return
    bot_dir = os.path.join(WECHAT_ROOT, "bots", bot_id)
    os.makedirs(bot_dir, exist_ok=True)
    tok_path = os.path.join(bot_dir, "context_token")
    old_tok = load_context_token(bot_id)
    with open(tok_path, "w", encoding="utf-8") as f:
        f.write(token.strip())
    # 如果收到了新的 context_token，重置已发送计数为 0（每个新 token 有 10 条额度）
    if token.strip() != old_tok:
        quota_path = os.path.join(bot_dir, "token_quota.json")
        with open(quota_path, "w", encoding="utf-8") as f:
            json.dump({
                "context_token_sha": hashlib.sha256(token.strip().encode()).hexdigest()[:16],
                "used": 0,
                "max": 10,
                "updated_at": int(time.time())
            }, f, indent=2)

def inc_token_quota(bot_id: str):
    bot_dir = os.path.join(WECHAT_ROOT, "bots", bot_id)
    quota_path = os.path.join(bot_dir, "token_quota.json")
    data = {"used": 0, "max": 10, "updated_at": int(time.time())}
    if os.path.exists(quota_path):
        try:
            with open(quota_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["used"] = data.get("used", 0) + 1
    data["last_sent_at"] = int(time.time())
    with open(quota_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_token_quota(bot_id: str) -> dict:
    quota_path = os.path.join(WECHAT_ROOT, "bots", bot_id, "token_quota.json")
    if os.path.exists(quota_path):
        try:
            with open(quota_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"used": 0, "max": 10, "updated_at": 0}

def send_text_message(bot_id: str, text: str, context_token: str = None, to_user_id: str = None) -> dict:
    secret = load_bot_secret(bot_id)
    baseurl = secret.get("baseurl") or DEFAULT_BASE_URL
    bot_token = secret["bot_token"]
    target_user = to_user_id or secret.get("ilink_user_id")
    ctx_tok = context_token or load_context_token(bot_id)
    if not ctx_tok:
        raise RuntimeError(f"Bot {bot_id} 缺少 context_token，无法发送消息")

    client_id = f"openclaw-weixin:{int(time.time()*1000)}-{os.urandom(4).hex()}"
    payload = {
        "msg": {
            "from_user_id": "",
            "to_user_id": target_user,
            "client_id": client_id,
            "message_type": 2,
            "message_state": 2,
            "context_token": ctx_tok,
            "run_id": str(uuid.uuid4()),
            "item_list": [
                {
                    "type": 1,
                    "text_item": {
                        "text": text
                    }
                }
            ]
        },
        "base_info": base_info()
    }
    url = f"{baseurl.rstrip('/')}/ilink/bot/sendmessage"
    res = http_post_json(url, payload, bot_token=bot_token, timeout=20)
    if res.get("ret") == 0:
        inc_token_quota(bot_id)
    return res
