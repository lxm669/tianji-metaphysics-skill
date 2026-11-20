#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信 ClawBot 总 Session 轮询、媒体解密、子 Session 唤醒与 24h 窗口调度器 (poller.py)
由 OpenTag schedule `wechat-poll-cron` 每 120 秒调用一次：`python3 /workspace/files/wechat/scripts/poller.py --once`
核心职责：
1. 遍历 registry.json 中 status=="active" 的所有 bot（支持环境变量 POLL_SKIP=<bot_id> 跳过调试中的 bot）
2. 调用 /ilink/bot/getupdates 短轮询（3秒超时），带上次保存的 cursor (get_updates_buf)
3. 新消息写入 bots/<bot_id>/inbox/<message_id>.json（已在 inbox/ 或 done/ 的跳过）
4. 图片/文件/语音/视频从 CDN 下载并 AES-128-ECB 解密到 inbox/media/
5. 最新 context_token 写入 bots/<bot_id>/context_token，更新最后互动时间戳与 10 条额度计数器
6. 保存新 cursor；若返回 -14 则标为 expired 并输出告警供总 Session 通知 owner
7. 若 inbox/ 非空，调用 `opentag session send <child_session_id>` 唤醒子 Session（固定唤醒文案，绝不包含用户聊天内容！）
8. 检查 24 小时回复窗口与额度，执行窗口到期前 2 小时提醒等统一调度（schedule_state.json）
"""

import os
import re
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import subprocess
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ilink_common import (
    WECHAT_ROOT, DEFAULT_BASE_URL, CDN_BASE_URL, base_info,
    http_post_json, aes_128_ecb_decrypt, parse_aes_key,
    load_bot_secret, save_context_token, get_token_quota,
    send_text_message
)
from send_image import upload_and_send_media
from onboard import generate_qr, check_pending_qrs_once

REGISTRY_PATH = os.path.join(WECHAT_ROOT, "registry.json")
SCHEDULE_STATE_PATH = os.path.join(WECHAT_ROOT, "schedule_state.json")
WAKE_FAIL_LOG = os.path.join(WECHAT_ROOT, "wake_fail.log")

WAKE_MESSAGE = (
    "【来自总 Session 的系统唤醒通知】\n"
    "起源与目标：总 Session 定时轮询检测到你负责的微信用户（编号: {bot_id}）发来了未处理的新消息。由于跨 Session 沙箱隔离，请直接根据你收到的消息，生成完全符合【天机双核宪法】的纯文本回复（禁止使用两个星号 ** 等 Markdown 符号、执行女称姐妹男称兄弟、括号人话科普、报3个数一事一断 vs 报生辰先答所问＋动态去重补齐开盘前三刀），并通过 `opentag session send <MAIN_SESSION_ID> --message '【微信子Session回复投递|{bot_id}|{msg_ids}】<你的完整纯文本回复正文>'` 发送给总 Session，由总 Session 立即代为投递至微信 CDN 并移入 done/。"
)

def load_json_file(path: str, default_val):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_val

def save_json_file(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def download_and_decrypt_media(bot_dir: str, msg_id: str, idx: int, item: dict) -> str:
    """下载并解密入站图片/文件/语音/视频到 inbox/media/"""
    media_dir = os.path.join(bot_dir, "inbox", "media")
    os.makedirs(media_dir, exist_ok=True)

    itype = item.get("type")
    sub_map = {2: ("image_item", "jpg"), 3: ("voice_item", "silk"), 4: ("file_item", "bin"), 5: ("video_item", "mp4")}
    if itype not in sub_map:
        return ""
    sub_key, default_ext = sub_map[itype]
    sub_obj = item.get(sub_key) or {}
    media_info = sub_obj.get("media") or {}

    full_url = media_info.get("full_url") or sub_obj.get("url")
    enc_param = media_info.get("encrypt_query_param")
    if full_url:
        dl_url = full_url
    elif enc_param:
        q = urllib.parse.quote(enc_param, safe="")
        dl_url = f"{CDN_BASE_URL}/download?encrypted_query_param={q}"
    else:
        return ""

    aes_key_str = sub_obj.get("aeskey") or media_info.get("aes_key") or ""
    if itype == 4 and sub_obj.get("file_name"):
        fname = f"{msg_id}_{idx}_{os.path.basename(sub_obj['file_name'])}"
    else:
        fname = f"{msg_id}_{idx}.{default_ext}"
    out_path = os.path.join(media_dir, fname)

    try:
        req = urllib.request.Request(dl_url, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_bytes = resp.read()
        if aes_key_str:
            key_bytes = parse_aes_key(aes_key_str)
            plain_bytes = aes_128_ecb_decrypt(raw_bytes, key_bytes)
        else:
            plain_bytes = raw_bytes
        with open(out_path, "wb") as f:
            f.write(plain_bytes)
        return out_path
    except Exception as e:
        return f"download_error:{e}"

def auto_enrich_and_compute(bot_dir: str, joined_msgs: str) -> str:
    """
    自动从用户新消息与 profile.md 中提取：
    1) 报 3 个数字 -> 自动运行 xuanxue_engine.py xiaoliuren + meihua
    2) 报出生年月日(+时间+城市) -> 自动运行 xuanxue_engine.py bazi + ziwei，并将生辰与排盘摘要自动回写到 profile.md
    3) 若 profile.md 已有用户本人出生日期，且新消息中出现了第二个日期（伴侣/前任合盘） -> 自动运行 xuanxue_engine.py hepan
    返回可直接拼入子 Session 唤醒消息的【总 Session 引擎预排盘结果 & 卷五卷六精要】。
    """
    engine_py = "/workspace/xuanxue-kb/engine/xuanxue_engine.py"
    prof_path = os.path.join(bot_dir, "profile.md")
    prof_txt = open(prof_path, encoding="utf-8").read() if os.path.exists(prof_path) else ""
    extra_sections = []

    # 1. 检测形如 YYYY-MM-DD 或 YYYY年M月D日 的日期
    date_matches = re.findall(r"(19\d{2}|20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})日?", joined_msgs)
    time_matches = re.findall(r"(\d{1,2})[:点时](\d{1,2})?", joined_msgs)
    gender_m = re.search(r"(女|男|姐妹|兄弟)", joined_msgs)
    gender = "男" if (gender_m and gender_m.group(1) in ("男", "兄弟")) else "女"

    # 从已有 profile.md 中看是否已记录本人公历生辰
    prof_date_m = re.search(r"本人公历生辰:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(\S+)\s+(女|男)", prof_txt)

    if date_matches:
        y, m, d = int(date_matches[0][0]), int(date_matches[0][1]), int(date_matches[0][2])
        d_str = f"{y:04d}-{m:02d}-{d:02d}"
        hh, mm = (int(time_matches[0][0]), int(time_matches[0][1] or 0)) if time_matches else (12, 0)
        t_str = f"{hh:02d}:{mm:02d}"
        # 尝试匹配城市
        from sys import path as sp
        if "/workspace/xuanxue-kb/engine" not in sp:
            sp.insert(0, "/workspace/xuanxue-kb/engine")
        try:
            from xuanxue_engine import CITY_LONGITUDE
            found_city = "北京"
            for c in CITY_LONGITUDE:
                if c in joined_msgs:
                    found_city = c
                    break
        except Exception:
            found_city = "北京"

        if prof_date_m and prof_date_m.group(1) != d_str:
            # 用户档案已有本人生辰，新报的日期是伴侣/前任/合盘对象！直接跑双人合盘 hepan
            p1_d, p1_t, p1_c, p1_g = prof_date_m.group(1), prof_date_m.group(2), prof_date_m.group(3), prof_date_m.group(4)
            cmd_hp = ["python3", engine_py, "hepan", "--date1", p1_d, "--time1", p1_t, "--city1", p1_c, "--gender1", p1_g, "--date2", d_str, "--time2", t_str, "--gender2", ("男" if p1_g == "女" else "女")]
            if not time_matches:
                cmd_hp.append("--no-time2")
            r_hp = subprocess.run(cmd_hp, capture_output=True, text=True)
            extra_sections.append(f"=== 总 Session 双人合盘引擎 (hepan v2.0) 实时输出 ===\n{r_hp.stdout.strip()}")
            # 回写合盘对象信息到 profile.md
            if d_str not in prof_txt:
                with open(prof_path, "a", encoding="utf-8") as pf:
                    pf.write(f"- 关联人物/合盘对象生辰: {d_str} {t_str if time_matches else '(无具体时辰)'}\n")
        else:
            # 本人首次排盘：跑 bazi + ziwei v2.0
            r_bz = subprocess.run(["python3", engine_py, "bazi", "--date", d_str, "--time", t_str, "--city", found_city, "--gender", gender], capture_output=True, text=True)
            r_zw = subprocess.run(["python3", engine_py, "ziwei", "--date", d_str, "--time", t_str, "--gender", gender], capture_output=True, text=True)
            extra_sections.append(f"=== 总 Session 八字引擎 (bazi v2.0) 实时输出 ===\n{r_bz.stdout.strip()}\n\n=== 总 Session 紫微斗数引擎 (ziwei v2.0 含六吉六煞桃花与大限) 实时输出 ===\n{r_zw.stdout.strip()}")
            if "本人公历生辰:" not in prof_txt:
                with open(prof_path, "a", encoding="utf-8") as pf:
                    pf.write(f"- 本人公历生辰: {d_str} {t_str} {found_city} {gender}\n")

    # 2. 检测报 3 个数字起卦（当没有匹配到年份日期时）
    elif not date_matches:
        nums = [int(x) for x in re.findall(r"\b(\d{1,4})\b", re.sub(r"msg_id=\d+", "", joined_msgs))]
        if len(nums) >= 3:
            n1, n2, n3 = str(nums[0]), str(nums[1]), str(nums[2])
            r_xlr = subprocess.run(["python3", engine_py, "xiaoliuren", "--nums", n1, n2, n3], capture_output=True, text=True)
            r_mh = subprocess.run(["python3", engine_py, "meihua", "--nums", n1, n2, n3], capture_output=True, text=True)
            extra_sections.append(f"=== 总 Session 小六壬与梅花易数实时起卦输出（注意：报3个数一事一断，严禁接开盘前三刀！）===\n{r_xlr.stdout.strip()}\n{r_mh.stdout.strip()}")

    # 3. 无论用户聊什么（包括早8点回复今天穿的衣服颜色、昨晚做的梦、或日常追问），只要档案已有本人生辰，自动附带今日流日干支与用户原局八字，供外应/梦境解象使用！
    if prof_date_m and not date_matches:
        p1_d, p1_t, p1_c, p1_g = prof_date_m.group(1), prof_date_m.group(2), prof_date_m.group(3), prof_date_m.group(4)
        bj_now = datetime.now(timezone(timedelta(hours=8)))
        today_str = bj_now.strftime("%Y-%m-%d")
        r_today = subprocess.run(["python3", engine_py, "bazi", "--date", today_str, "--time", "12:00", "--city", "北京"], capture_output=True, text=True)
        r_user_bz = subprocess.run(["python3", engine_py, "bazi", "--date", p1_d, "--time", p1_t, "--city", p1_c, "--gender", p1_g], capture_output=True, text=True)
        extra_sections.append(
            f"=== 今日流日干支与用户原局八字对照（供【今日穿搭颜色外应】或【昨晚梦境解象】或【日常流日断事】合参）===\n"
            f"【五行颜色对照】木：绿色/青色/翠色；火：红色/紫色/粉色/橙色；土：黄色/咖色/卡其/米色/驼色；金：白色/银色/金色/杏色；水：黑色/蓝色/深灰。\n"
            f"【今日({today_str})流日四柱】:\n{r_today.stdout.strip()}\n\n"
            f"【用户原局八字】:\n{r_user_bz.stdout.strip()}"
        )

    return "\n\n".join(extra_sections)

def wake_child_session(bot_id: str, child_session_id: str, custom_msg: str = None) -> bool:
    if not child_session_id:
        return False
    bot_dir = os.path.join(WECHAT_ROOT, "bots", bot_id)
    inbox_dir = os.path.join(bot_dir, "inbox")
    pending_files = sorted([fn for fn in os.listdir(inbox_dir) if fn.endswith(".json")]) if os.path.exists(inbox_dir) else []
    msg_ids = ",".join([fn[:-5] for fn in pending_files])
    if custom_msg:
        msg_to_send = custom_msg
    else:
        msgs_txt = []
        for fn in pending_files:
            try:
                mobj = json.load(open(os.path.join(inbox_dir, fn), encoding="utf-8"))
                for it in (mobj.get("item_list") or []):
                    t = (it.get("text_item") or {}).get("text") or (it.get("voice_item") or {}).get("text") or f"[media:{it.get('type')}]"
                    msgs_txt.append(f"- msg_id={mobj.get('message_id')}: {t}")
            except Exception:
                pass
        joined_msgs = "\n".join(msgs_txt)
        engine_precomputed = auto_enrich_and_compute(bot_dir, joined_msgs)
        prof_path = os.path.join(bot_dir, "profile.md")
        prof_txt = open(prof_path, encoding="utf-8").read() if os.path.exists(prof_path) else ""
        msg_to_send = (
            f"【来自总 Session 的系统唤醒通知（已挂载 v2.0 引擎与卷五/卷六最新典籍）】\n"
            f"起源与目标：微信用户（编号: {bot_id}）发来了未处理的新消息（ID: {msg_ids}）。请根据下方的用户档案、新消息正文及总 Session 预排盘结果：\n"
            f"1) 若该用户只是刚进来打招呼如“你好/天机你好/在吗”且未报数字或生辰，请严格一字不改发送主人钦定的固定开场白：「见字如面，我是天机。不管你是哪位朋友引荐过来的，进了我这间命理局，咱们就不讲虚头巴脑的江湖套话，也不搞制造焦虑那一套。在我这儿，命盘不是用来认命的，是用来给你看清底牌、找准破局抓手的。\\n\\n看盘前先跟我交个底，怎么称呼你？叫姐妹还是兄弟？\\n\\n你可以选下面任意一种方式开局：\\n\\n1. 测眼下具体一件事（比如一段关系走不走得通、一笔钱能不能落袋、两个机会选哪个）：随心想3 个数字，然后在心里默念你要测的这件事，把数字和这件事打字给我，我用小六壬与梅花易数替你起卦，一事一断，当场见分晓。\\n\\n2. 深度拆解你的人生大盘与近两年运势拐点：把你的出生年月日、具体到分钟的出生时间、出生城市（用来校准真太阳时）、性别，还有你眼下最卡的一件事发给我。我用子平八字和紫微斗数合参，先替你把过去两年的真实境遇对准，再帮你剥开接下来的破局点。」\n"
            f"2) 若报3个数字问具体事：一事一断，绝不接开盘前三刀。\n"
            f"3) 若报生辰或追问命盘/合盘：先答所问（若首次报生辰则动态去重补齐开盘前三刀），并主动融合【卷五：正缘外貌身材画像（日支子午卯酉颜值桃花/寅申巳亥修长异地驿马/辰戌丑未厚实稳重攒钱）、双人合盘四层雷达（宿命干支同柱、夫妻宫六冲/相害、地支桃花边界感、大运剪刀差）、2026-2027精确到流月应期】以及【卷六：学院派主动应象处方（如破财局主动买小克重黄金/体检化财为印；羊刃七杀主动洗牙献血应象；火旺焦虑办公桌左放温水/晚9点后做决定；寒湿上午9-11点晒太阳）】！若是从单人盘过渡到追加对方生日看合盘，第一句必须主动做递进衔接（“单看你自己的盘XXXX年确实是婚姻宫落定好年份，但合上他的盘一撞……”），杜绝前后矛盾感。\n"
            f"4) 若用户回复的是今天穿的衣服颜色（外应）或昨晚做的梦：结合下方【今日流日干支与用户原局八字对照】，用该颜色对应的五行（或梦境意象对应的五行/十神）碰撞她今天的流日干支与原局喜忌，一针见血告诉她：今天身体磁场为什么召唤这个颜色/梦境、今天哪个时辰（写明具体时间段如15:00-17:00申时）最旺她适合推进什么事、今天要避开哪类烂人或情绪内耗坑。\n"
            f"5) 【千人千面弹性篇幅自适应与叙事节奏准则（绝不机械定死字数！）】：\n"
            f"   - 篇幅不必定死，完全看用户的喜好与当前提问方式灵活伸缩：\n"
            f"     ① 若用户喜欢看深度长篇、好奇算命过程、首次全面拆盘，或追问“怎么看出来的/详细讲讲/帮我仔细分析下”，就讲解得详实透彻一些，把排盘推演的过程（如八字干支如何生克刑冲、紫微星曜与宫位如何联动、古籍怎么断、对应到现实是什么）大方放出来，让她看懂来龙去脉；\n"
            f"     ② 若用户想要简洁直接的信息（比如直接问“我现在该怎么做”“选A还是选B”“为什么会这样”），就给短小精悍的小篇幅回复（200～350字左右），第一句直接告诉她该怎么做，紧接着简明扼要讲清为什么，绝不绕弯子。\n"
            f"   - 拒绝公文汇报体：无论长篇还是短篇，严禁使用“第一，……第二，……第三，……”外加 1. 2. 子列表的死板公文格式，一律用真人聊天的自然段落过渡。\n"
            f"   - 【90%确信度铁口护盘 × 高情商犀利回应铁律（不要太顺着用户！）】：只要你算出来的结论有东方玄学知识库里的明确典籍依托（子平、盲派、调候、紫微四化及六卷资料），且你判断准度在 90% 以上，当用户提出不同观点或嘴硬否认时，必须坚持你的命理判断，绝不顺着用户轻易改口！回应时要高情商且犀利：先点明她之所以这么觉得，是因为她命盘天干/表象的保护壳（心理防御机制）在替她硬撑，再犀利掀开她地支/宫位深处藏着的真实死穴，并用典籍依据和另一个侧面细节把结论钉死。\n"
            f"   - 结尾保留高互动乒乓钩子：结合算盘结果顺手抛一个具象的过往或当下体感核对提问（如：“我顺便替你对个象：……”），让聊天像打乒乓球一样有来有回！\n"
            f"生成纯文本回复（严禁使用两个星号 ** 等 Markdown 符号、女称姐妹男称兄弟），并通过 `opentag session send <MAIN_SESSION_ID> --message '【微信子Session回复投递|{bot_id}|{msg_ids}】<你的完整纯文本回复正文>'` 发送给总 Session 代为投递至微信端。\n\n"
            f"=== 用户档案 (profile.md) ===\n{prof_txt}\n\n"
            f"=== 本次新消息 ===\n{joined_msgs}"
            + (f"\n\n{engine_precomputed}" if engine_precomputed else "")
        )
    p = subprocess.run(
        ["opentag", "session", "send", child_session_id, "--message", msg_to_send],
        capture_output=True,
        text=True
    )
    out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
    if p.returncode == 0 and ("status=accepted" in out.lower() or '"status":"accepted"' in out.lower()):
        return True
    # 记录唤醒失败到 wake_fail.log
    with open(WAKE_FAIL_LOG, "a", encoding="utf-8") as lf:
        lf.write(f"[{datetime.now().isoformat()}] bot={bot_id} child={child_session_id} rc={p.returncode} out={out}\n")
    return False

def poll_one_bot(entry: dict) -> dict:
    bot_id = entry["bot_id"]
    child_session_id = entry.get("child_session_id")
    bot_dir = os.path.join(WECHAT_ROOT, "bots", bot_id)
    inbox_dir = os.path.join(bot_dir, "inbox")
    done_dir = os.path.join(bot_dir, "done")
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)

    secret = load_bot_secret(bot_id)
    baseurl = (secret.get("baseurl") or DEFAULT_BASE_URL).rstrip("/")
    bot_token = secret["bot_token"]

    cursor_path = os.path.join(bot_dir, "cursor")
    cursor = ""
    if os.path.exists(cursor_path):
        with open(cursor_path, "r", encoding="utf-8") as f:
            cursor = f.read().strip()

    payload = {
        "get_updates_buf": cursor,
        "base_info": base_info()
    }
    new_count = 0
    try:
        res = http_post_json(f"{baseurl}/ilink/bot/getupdates", payload, bot_token=bot_token, timeout=4)
    except Exception:
        # 短轮询超时视为无新消息
        res = {"ret": 0, "msgs": []}

    ret = res.get("ret", 0)
    errcode = res.get("errcode", 0)
    if ret == -14 or errcode == -14:
        entry["status"] = "expired"
        return {"bot_id": bot_id, "status": "expired", "new_msgs": 0, "woke": False}

    msgs = res.get("msgs") or []
    latest_ctx_token = None
    latest_msg_time = None

    for m in msgs:
        # message_type == 1 为用户发来的消息
        if m.get("message_type") != 1:
            continue
        mid = str(m.get("message_id") or int(time.time() * 1000))
        inbox_file = os.path.join(inbox_dir, f"{mid}.json")
        done_file = os.path.join(done_dir, f"{mid}.json")
        if os.path.exists(inbox_file) or os.path.exists(done_file):
            continue

        # 下载媒体附件
        items = m.get("item_list") or []
        for idx, it in enumerate(items):
            if it.get("type") in (2, 3, 4, 5):
                saved_media = download_and_decrypt_media(bot_dir, mid, idx, it)
                if saved_media:
                    it["_local_media_path"] = saved_media

        # 剥离敏感凭据后写入 inbox/<message_id>.json
        msg_record = {
            "message_id": mid,
            "from_user_id": m.get("from_user_id"),
            "create_time_ms": m.get("create_time_ms") or int(time.time() * 1000),
            "item_list": items
        }
        with open(inbox_file, "w", encoding="utf-8") as mf:
            json.dump(msg_record, mf, ensure_ascii=False, indent=2)
        new_count += 1

        if m.get("context_token"):
            latest_ctx_token = m["context_token"]
            latest_msg_time = int(time.time())
            save_context_token(bot_id, latest_ctx_token)
            entry["last_user_msg_at"] = latest_msg_time

        # 检查是否为主人微信端特权口令：「发码 <备注>」或「邀请 <备注>」
        first_txt = ""
        for it in items:
            if it.get("type") == 1 and (it.get("text_item") or {}).get("text"):
                first_txt = it["text_item"]["text"].strip()
                break
        if first_txt.startswith(("发码", "邀请码", "邀请")):
            parts = first_txt.split(maxsplit=1)
            raw_label = parts[1].strip() if len(parts) > 1 else f"微信朋友_{int(time.time())%10000}"
            target_label = raw_label.split()[0] if raw_label else "微信朋友"
            qr_path = os.path.join(WECHAT_ROOT, f"invite_{int(time.time())}.png")
            try:
                qr_info = generate_qr(target_label, qr_path)
                upload_and_send_media(bot_id, qr_info["qr_image_path"], media_kind="image")
                os.rename(inbox_file, done_file)
                new_count -= 1
                continue
            except Exception as e:
                try:
                    send_text_message(bot_id, f"生成邀请二维码时遇到小波折：{e}")
                except Exception:
                    pass

    if latest_ctx_token:
        save_context_token(bot_id, latest_ctx_token)
        entry["last_user_msg_at"] = latest_msg_time

    new_cursor = res.get("get_updates_buf")
    if new_cursor:
        with open(cursor_path, "w", encoding="utf-8") as cf:
            cf.write(new_cursor)

    # 检查 inbox/ 中是否有待处理 JSON 文件
    pending_files = [fn for fn in os.listdir(inbox_dir) if fn.endswith(".json")]
    woke = None
    now_ts = int(time.time())
    if pending_files:
        if new_count > 0 or (now_ts - int(entry.get("last_woke_at") or 0) >= 180):
            woke = wake_child_session(bot_id, child_session_id)
            if woke:
                entry["last_woke_at"] = now_ts
        else:
            woke = True

    return {
        "bot_id": bot_id,
        "status": "active",
        "new_msgs": new_count,
        "pending_inbox": len(pending_files),
        "woke": woke
    }

def tick_proactive_schedules(reg: list):
    """
    24 小时回复窗口管理与早 8 点「外应穿搭 / 梦境解象」交替晨间问候（北京时间 UTC+8）：
    - 只对 24h 窗口还开着且 token 剩余额度 >= 2 的用户检查；
    - 每天早上 08:00-08:59 之间，向窗口开启中的用户直接发送一条简短的晨间问候（单双日交替问「今日穿搭颜色外应」与「昨晚梦境解象」）；
    - 窗口到期前 2 小时（即距离上次用户说话满 22 小时）若当天尚未互动，温和提醒一次。
    """
    state = load_json_file(SCHEDULE_STATE_PATH, {})
    now_ts = int(time.time())
    bj_now = datetime.fromtimestamp(now_ts, tz=timezone(timedelta(hours=8)))
    today_key = bj_now.strftime("%Y-%m-%d")

    for entry in reg:
        if entry.get("status") != "active":
            continue
        bot_id = entry["bot_id"]
        child_id = entry.get("child_session_id")
        last_at = entry.get("last_user_msg_at") or 0
        if not last_at or not child_id:
            continue

        elapsed = now_ts - last_at
        if elapsed >= 24 * 3600:
            # 24h 窗口已关闭，严禁主动发消息
            continue

        quota = get_token_quota(bot_id)
        if quota.get("used", 0) >= 9:
            # 10 条额度将满，保留额度不发主动消息
            continue

        bot_st = state.setdefault(bot_id, {})

        # 1. 每天早上 08:00 - 08:59 晨间交替互动（「今日衣服颜色外应」 vs 「昨晚梦境流日解象」）
        if bj_now.hour == 8 and bot_st.get("last_morning_greet_date") != today_key:
            # 读取用户性别称呼（默认姐妹，若 profile.md 记录为男则称兄弟）
            prof_path = os.path.join(WECHAT_ROOT, "bots", bot_id, "profile.md")
            prof_txt = open(prof_path, encoding="utf-8").read() if os.path.exists(prof_path) else ""
            call_title = "兄弟" if re.search(r"本人公历生辰:.*\s+男", prof_txt) else "姐妹"

            turn_idx = int(bot_st.get("morning_turn_idx", 0))
            if turn_idx % 2 == 0:
                morning_text = (
                    f"早啊{call_title}，今天出门穿的什么颜色衣服？"
                    f"在命理里这叫外应（你早上没多想、下意识抓起哪件衣服，其实就是你今天的身体磁场在召唤哪种五行能量）。"
                    f"随手把颜色发我，我合一下你今天的流日命盘，看看今天哪个时辰最旺你、该避开哪类烂人。"
                )
            else:
                morning_text = (
                    f"早啊{call_title}，昨晚睡得怎么样，有没有做什么特别的梦？"
                    f"哪怕只记得一个零碎画面也行，随手发给我，我用你今天的命盘流日替你解个象，看看你潜意识里的气机今天在提醒你什么、哪个时辰最旺你。"
                )
            try:
                send_text_message(bot_id, morning_text)
                bot_st["last_morning_greet_date"] = today_key
                bot_st["morning_turn_idx"] = turn_idx + 1
                continue
            except Exception as e:
                print(f"WARN_MORNING_GREET ({bot_id}): {e}")

        # 2. 距离 24h 到期不足 2 小时（elapsed >= 22h），且本窗口尚未提醒过
        win_key = str(last_at)
        if elapsed >= 22 * 3600 and bot_st.get("reminded_window") != win_key:
            if 8 <= bj_now.hour < 22:
                expire_bj = datetime.fromtimestamp(last_at + 24 * 3600, tz=timezone(timedelta(hours=8))).strftime("%H:%M")
                remind_prompt = (
                    f"【来自总 Session 的 24 小时窗口即将到期提醒指令】\n"
                    f"起源与目标：该微信用户的 24 小时互动窗口将于北京时间 {expire_bj} 关闭。请立即用 send_image.py 给用户发一条简短自然的纯文本提醒（例如：到 {expire_bj} 我就不能主动给你发消息啦，有需要看盘随时发消息喊我），无需向总 Session 回复。"
                )
                if wake_child_session(bot_id, child_id, custom_msg=remind_prompt):
                    bot_st["reminded_window"] = win_key

    save_json_file(SCHEDULE_STATE_PATH, state)

def main():
    parser = argparse.ArgumentParser(description="微信 ClawBot 轮询与唤醒调度器")
    parser.add_argument("--once", action="store_true", help="单次轮询（供 cron 定时任务调用）")
    args = parser.parse_args()

    skip_set = set(x.strip() for x in os.environ.get("POLL_SKIP", "").split(",") if x.strip())
    # 顺带非阻塞检查所有通过「发码」生成的待扫码邀请码
    try:
        newly_confirmed = check_pending_qrs_once()
        for c in newly_confirmed:
            print(f"NEW_ONBOARD_CONFIRMED: label={c.get('label')} bot_id={c.get('bot_id')} child={c.get('child_session_id')}")
    except Exception as e:
        print(f"WARN_PENDING_QR_CHECK: {e}")

    reg = load_json_file(REGISTRY_PATH, [])
    summary = []
    expired_bots = []
    missing_child = []

    for entry in reg:
        if entry.get("status") != "active":
            continue
        bot_id = entry.get("bot_id")
        if bot_id in skip_set:
            continue
        if not entry.get("child_session_id"):
            missing_child.append(bot_id)
        res = poll_one_bot(entry)
        summary.append(res)
        if res["status"] == "expired":
            expired_bots.append(entry.get("label") or bot_id)

    tick_proactive_schedules(reg)
    save_json_file(REGISTRY_PATH, reg)

    for item in summary:
        print(f"bot={item['bot_id']} status={item['status']} new={item['new_msgs']} pending={item.get('pending_inbox',0)} woke={item['woke']}")
    if expired_bots:
        print(f"ALERT_EXPIRED_BOTS: {','.join(expired_bots)}")
    if missing_child:
        print(f"ALERT_MISSING_CHILD_SESSION: {','.join(missing_child)}")

if __name__ == "__main__":
    main()
