#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信 ClawBot 图片与文件发送工具 (send_image.py)
流程：
1. 读取本地图片或文件 -> 计算明文 rawsize / rawfilemd5 / AES-128-ECB 加密后 filesize
2. POST /ilink/bot/getuploadurl 拿 upload_full_url 或 upload_param
3. AES-128-ECB 加密文件并 POST 到微信 CDN，读取响应头 x-encrypted-param
4. POST /ilink/bot/sendmessage 发送 image_item (type=2) 或 file_item (type=4)，带最新 context_token
注意：不发 voice_item 原生语音条（实测静默丢弃），音频一律作为 --file 发送！
"""

import os
import sys
import json
import time
import uuid
import base64
import hashlib
import argparse
import urllib.request
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ilink_common import (
    DEFAULT_BASE_URL, CDN_BASE_URL, base_info, http_post_json,
    aes_128_ecb_encrypt, load_bot_secret, load_context_token, inc_token_quota
)

def upload_and_send_media(bot_id: str, file_path: str, media_kind: str = "image", context_token: str = None, to_user_id: str = None) -> dict:
    secret = load_bot_secret(bot_id)
    baseurl = (secret.get("baseurl") or DEFAULT_BASE_URL).rstrip("/")
    bot_token = secret["bot_token"]
    target_user = to_user_id or secret.get("ilink_user_id")
    ctx_tok = context_token or load_context_token(bot_id)
    if not ctx_tok:
        raise RuntimeError(f"Bot {bot_id} 缺少 context_token，无法发送媒体")

    with open(file_path, "rb") as f:
        plaintext = f.read()

    rawsize = len(plaintext)
    rawfilemd5 = hashlib.md5(plaintext).hexdigest()
    aeskey_bytes = os.urandom(16)
    aeskey_hex = aeskey_bytes.hex()
    filekey = os.urandom(16).hex()

    ciphertext = aes_128_ecb_encrypt(plaintext, aeskey_bytes)
    filesize = len(ciphertext)

    # media_type: 1=IMAGE, 2=VIDEO, 3=FILE
    media_type_num = 1 if media_kind == "image" else 3

    upload_req = {
        "filekey": filekey,
        "media_type": media_type_num,
        "to_user_id": target_user,
        "rawsize": rawsize,
        "rawfilemd5": rawfilemd5,
        "filesize": filesize,
        "no_need_thumb": True,
        "aeskey": aeskey_hex,
        "base_info": base_info()
    }
    up_info = http_post_json(f"{baseurl}/ilink/bot/getuploadurl", upload_req, bot_token=bot_token, timeout=20)
    upload_full_url = up_info.get("upload_full_url")
    upload_param = up_info.get("upload_param")
    if upload_full_url:
        cdn_url = upload_full_url
    elif upload_param:
        q_param = urllib.parse.quote(upload_param, safe="")
        q_key = urllib.parse.quote(filekey, safe="")
        cdn_url = f"{CDN_BASE_URL}/upload?encrypted_query_param={q_param}&filekey={q_key}"
    else:
        raise RuntimeError(f"getuploadurl 失败: {json.dumps(up_info, ensure_ascii=False)}")

    req = urllib.request.Request(
        cdn_url,
        data=ciphertext,
        headers={"Content-Type": "application/octet-stream"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        enc_query_param = resp.headers.get("x-encrypted-param") or resp.headers.get("X-Encrypted-Param")
        if not enc_query_param:
            body_txt = resp.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"CDN 上传未返回 x-encrypted-param, body={body_txt}")

    aes_key_b64 = base64.b64encode(aeskey_hex.encode("ascii")).decode("ascii")
    cdn_media = {
        "encrypt_query_param": enc_query_param,
        "aes_key": aes_key_b64,
        "encrypt_type": 1
    }

    if media_kind == "image":
        item = {
            "type": 2,
            "image_item": {
                "media": cdn_media,
                "mid_size": filesize
            }
        }
    else:
        item = {
            "type": 4,
            "file_item": {
                "media": cdn_media,
                "file_name": os.path.basename(file_path),
                "md5": rawfilemd5,
                "len": str(rawsize)
            }
        }

    client_id = f"openclaw-weixin:{int(time.time()*1000)}-{os.urandom(4).hex()}"
    send_payload = {
        "msg": {
            "from_user_id": "",
            "to_user_id": target_user,
            "client_id": client_id,
            "message_type": 2,
            "message_state": 2,
            "context_token": ctx_tok,
            "run_id": str(uuid.uuid4()),
            "item_list": [item]
        },
        "base_info": base_info()
    }
    res = http_post_json(f"{baseurl}/ilink/bot/sendmessage", send_payload, bot_token=bot_token, timeout=20)
    if res.get("ret", 0) == 0:
        inc_token_quota(bot_id)
    return res

def main():
    parser = argparse.ArgumentParser(description="发送微信 ClawBot 텍스트/图片/文件消息")
    parser.add_argument("--bot-id", required=True, help="bots/<bot_id> 目录名")
    parser.add_argument("--image", help="要发送的图片路径")
    parser.add_argument("--file", help="要发送的文件路径（含 mp3 音频文件）")
    parser.add_argument("--text", help="要发送的纯文本消息")
    parser.add_argument("--context-token", default=None, help="指定 context_token（默认读取 bots/<bot_id>/context_token）")
    args = parser.parse_args()

    from ilink_common import send_text_message
    results = []
    if args.text:
        r = send_text_message(args.bot_id, args.text, context_token=args.context_token)
        results.append({"type": "text", "res": r})
    if args.image:
        r = upload_and_send_media(args.bot_id, args.image, media_kind="image", context_token=args.context_token)
        results.append({"type": "image", "res": r})
    if args.file:
        r = upload_and_send_media(args.bot_id, args.file, media_kind="file", context_token=args.context_token)
        results.append({"type": "file", "res": r})
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
