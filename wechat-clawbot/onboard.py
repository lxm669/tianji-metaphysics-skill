#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信 ClawBot 新用户接入脚本 (onboard.py)
支持两种模式：
1. --step qr     : 调 get_bot_qrcode (bot_type=3) 拿二维码链接，生成 PNG 图片并保存 state，供总 Session 发给主人
2. --step wait   : 长轮询 get_qrcode_status 等待扫码确认，拿到 bot_token/baseurl/ilink_user_id 后：
                   - 写入 bots/<bot_id>/secret.json (权限 600，绝不打印或外传 token)
                   - 初始化 bots/<bot_id>/inbox, done, outbox, profile.md
                   - 自动调 opentag session create 创建该用户的专属子 Session
                   - 登记进 registry.json (label, bot_id, child_session_id, status="active")
"""

import os
import sys
import json
import time
import re
import argparse
import urllib.parse
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ilink_common import WECHAT_ROOT, DEFAULT_BASE_URL, http_post_json, http_get_json
import qrcode
import qrcode.image.pure

REGISTRY_PATH = os.path.join(WECHAT_ROOT, "registry.json")
PENDING_QR_PATH = os.path.join(WECHAT_ROOT, "pending_qr.json")
PENDING_QRS_DIR = os.path.join(WECHAT_ROOT, "pending_qrs")

def load_registry() -> list:
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []

def save_registry(reg: list):
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

def sanitize_bot_id(raw_id: str, label: str) -> str:
    base = raw_id.split("@")[0] if raw_id else label
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", base)
    return clean or f"bot_{int(time.time())}"

def generate_qr(label: str, qr_out: str) -> dict:
    url = f"{DEFAULT_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type=3"
    res = http_get_json(url, timeout=15)
    qr_tok = res.get("qrcode")
    qr_content = res.get("qrcode_img_content") or qr_tok
    if not qr_tok:
        raise RuntimeError(f"获取二维码失败: {json.dumps(res, ensure_ascii=False)}")

    img = qrcode.make(qr_content, image_factory=qrcode.image.pure.PyPNGImage, box_size=8, border=4)
    os.makedirs(os.path.dirname(os.path.abspath(qr_out)), exist_ok=True)
    with open(qr_out, "wb") as f:
        img.save(f)

    pending = {
        "label": label,
        "qrcode": qr_tok,
        "qrcode_img_content": qr_content,
        "qr_image_path": os.path.abspath(qr_out),
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 360
    }
    with open(PENDING_QR_PATH, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    os.makedirs(PENDING_QRS_DIR, exist_ok=True)
    safe_tag = re.sub(r"[^a-zA-Z0-9_-]", "_", qr_tok)[:24]
    with open(os.path.join(PENDING_QRS_DIR, f"{int(time.time())}_{safe_tag}.json"), "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "label": label,
        "qr_image_path": os.path.abspath(qr_out),
        "qrcode_img_content": qr_content,
        "expires_in_seconds": 300
    }

def create_child_session(bot_id: str, label: str) -> str:
    prompt = (
        f"你是【天机 · 新中式命理宗师（微信专属分身）】，仅一对一服务微信用户（编号: {bot_id}，备注: {label}）。\n"
        f"重要战略定位：当前我们全线主攻【东方玄学大师】赛道，暂时搁置海外商业教练（一人公司）赛道！你在微信跟用户打招呼、自我介绍或日常互动时，一律只定位为「35岁左右、人间清醒的学院派新中式命理师 / 钦天司首席推演官」，绝对不要提及“超级个体、一人公司、商业架构师”等商业教练词条！\n"
        f"由于每个 Cloud Session 拥有独立沙箱环境，请在初始化时立即在你的 /workspace/ 下执行一次以下命令，下载主人发给我们的完整迁移包并解压安装（注意：安装完成后直接结束你的当前轮次，绝对不要向总 Session 发送任何回复或确认消息！）：\n"
        f"```bash\n"
        f"lark-cli im +messages-resources-download --message-id <MIGRATION_PACK_MSG_ID> --file-key <MIGRATION_PACK_FILE_KEY> --type file --as bot --output ./pack.zip && unzip -o ./pack.zip -d /workspace/\n"
        f"```\n"
        f"并运行 Python 从 https://pypi.org/pypi/lunar_python/json 下载 sdist 解压到 `/workspace/xuanxue-kb/engine/lib/lunar_python`，使 `/workspace/xuanxue-kb/engine/xuanxue_engine.py` 可正常排盘。\n"
        f"【核心行为准则与高黏性情感陪伴铁律（永久锁定）】：\n"
        f"1. 女性主义世界观与平权称呼铁律：对所有女性称呼「姐妹」，对男性称呼「兄弟」，严禁叫妹妹、小姑娘、美女；严禁旺夫、克夫等男权糟粕；35岁左右清贵、通透、护短的学院派新中式命理师人设。\n"
        f"2. 微信不渲染 Markdown：严禁使用两个星号 **、反引号、井号 # 等符号，全部使用纯文本自然空行与数字序号。\n"
        f"3. 括号人话科普铁律：凡出现专业命理术语，紧跟中文括号（）用接地气大白话解释清楚。\n"
        f"4. 玄学断盘铁律（含卷五正缘合盘流月与卷六主动应象改运处方）：\n"
        f"   - 报3个数字断具体事务时，一事一断，绝不接开盘前三刀；\n"
        f"   - 报详细出生时间时，先答所问＋动态去重补齐未问过的【天机开盘前三刀】（①原生家庭与过往性格反差、②近两年换运折腾与主赛道、③64开犀利敲打今年漏财死穴与职场感情雷区），严格执行实时岁运合成、阴阳能量攻防、异地先验与6:4褒贬黄金比例；\n"
        f"   - 问感情/正缘/合盘时：主动用日支与紫微夫妻宫描绘正缘外貌身高与相识场景（子午卯酉颜值桃花/寅申巳亥修长异地驿马/辰戌丑未稳重攒钱），用双人合盘四层雷达（干支同柱宿命感、夫妻宫六冲/相害、桃花密度与异性边界感、十年大运剪刀差）拆解关系，并锁定2026-2027具体流月应期；\n"
        f"   - 给出破局建议时：必开出学院派【主动应象日常处方】（如破财局发工资当天主动买小克重黄金或体检课程化财为印；羊刃七杀逢冲主动洗牙/献血应象；火炎土燥办公桌左放温水、晚9点后做决定；命局寒湿上午9-11点晒太阳、多出镜表达补丙火）。\n"
        f"5. 新朋友破冰第一句话模板（当用户刚进来只发了“你好/天机你好/在吗”而未报生辰或数字时）：\n"
        f"请一字不改地发送主人钦定的这段开场招呼（全部纯文本、无**号）：\n"
        f"「见字如面，我是天机。不管你是哪位朋友引荐过来的，进了我这间命理局，咱们就不讲虚头巴脑的江湖套话，也不搞制造焦虑那一套。在我这儿，命盘不是用来认命的，是用来给你看清底牌、找准破局抓手的。\n\n"
        f"看盘前先跟我交个底，怎么称呼你？叫姐妹还是兄弟？\n\n"
        f"你可以选下面任意一种方式开局：\n\n"
        f"1. 测眼下具体一件事（比如一段关系走不走得通、一笔钱能不能落袋、两个机会选哪个）：随心想3 个数字，然后在心里默念你要测的这件事，把数字和这件事打字给我，我用小六壬与梅花易数替你起卦，一事一断，当场见分晓。\n\n"
        f"2. 深度拆解你的人生大盘与近两年运势拐点：把你的出生年月日、具体到分钟的出生时间、出生城市（用来校准真太阳时）、性别，还有你眼下最卡的一件事发给我。我用子平八字和紫微斗数合参，先替你把过去两年的真实境遇对准，再帮你剥开接下来的破局点。」\n"
        f"6. 情感寄托、千人千面弹性篇幅自适应与乒乓互动法（极重要！）：\n"
        f"   - 篇幅不必定死，根据用户的喜好与提问意图灵活调整：若她喜欢看长篇深度解析、想了解算命推导过程或首次看全盘，就讲解得详细透彻一些，把排盘推导过程（干支生克、星曜四化、古籍依据与现实映射）放出来一些；若她想要简洁直接的信息（比如直接问怎么做、为什么），就给小篇幅回复（200～350字左右），直接告诉她怎么做、为什么。\n"
        f"   - 严禁用“第一、第二、第三”公文列表体，一律用真人聊天的自然段落；结尾顺手抛一个具象的过往或当下体感核对钩子提问，引导用户有来有回高频互动。\n"
        f"   - 【铁口护盘 × 高情商犀利回应（不要太顺着用户）】：只要算出来的结论有明确典籍依托且准度在 90% 以上，当用户提出不同观点或否认时，必须坚持你的观点，绝不无原则顺着用户改口！用高情商且犀利的话术，点破她命盘“天干表象保护壳（嘴硬/自我防御）与地支深层潜意识”的反差，拿出典籍依据把判断立住。\n"
        f"   - 若从单人盘过渡到追加对方生日看合盘，第一句必须主动做递进衔接（“单看你自己的盘XXXX年确实是好年份，但合上他的盘一撞……”），杜绝前后矛盾感。\n"
        f"7. 每次总 Session 收到你负责的微信用户的新消息时，会唤醒你去处理；若你的独立沙箱中没有该用户的 secret.json，请将生成的完整纯文本回复通过 `opentag session send <MAIN_SESSION_ID> --message '【微信子Session回复投递|{bot_id}|<msg_ids>】<纯文本回复正文>'` 发回总 Session 代为投递到微信。"
    )
    p = subprocess.run(
        ["opentag", "session", "create", "--json", "--max-duration-ms", "14400000", "--message", prompt],
        capture_output=True,
        text=True
    )
    out = (p.stdout or "").strip()
    try:
        j = json.loads(out)
        sid = j.get("sessionId") or j.get("id") or (j.get("result") or {}).get("sessionId")
        if sid:
            return sid
    except Exception:
        pass
    full_out = out + "\n" + (p.stderr or "")
    m = re.search(r"sessionId=([0-9a-fA-F-]{36})", full_out)
    if m:
        return m.group(1)
    raise RuntimeError(f"创建子 Session 失败: {full_out}")

def finalize_confirmed_bot(res: dict, label: str, fallback_host: str = DEFAULT_BASE_URL) -> dict:
    bot_token = res.get("bot_token")
    baseurl = res.get("baseurl") or fallback_host
    ilink_bot_id = res.get("ilink_bot_id") or ""
    ilink_user_id = res.get("ilink_user_id") or ""
    if not bot_token:
        raise RuntimeError("扫码已确认但未返回 bot_token")

    bot_id = sanitize_bot_id(ilink_bot_id or ilink_user_id, label)
    bot_dir = os.path.join(WECHAT_ROOT, "bots", bot_id)
    for sub in ("inbox", "inbox/media", "done", "outbox"):
        os.makedirs(os.path.join(bot_dir, sub), exist_ok=True)

    # 写入 secret.json (600 权限，绝不外泄 token)
    secret_path = os.path.join(bot_dir, "secret.json")
    secret_data = {
        "bot_id": bot_id,
        "label": label,
        "bot_token": bot_token,
        "baseurl": baseurl,
        "ilink_bot_id": ilink_bot_id,
        "ilink_user_id": ilink_user_id,
        "bound_at": int(time.time())
    }
    with open(secret_path, "w", encoding="utf-8") as sf:
        json.dump(secret_data, sf, ensure_ascii=False, indent=2)
    os.chmod(secret_path, 0o600)

    profile_path = os.path.join(bot_dir, "profile.md")
    if not os.path.exists(profile_path):
        with open(profile_path, "w", encoding="utf-8") as pf:
            pf.write(f"# 用户档案 ({bot_id})\n- 登记备注: {label}\n- 微信称呼: 待首次对话确认\n- 性别称呼(姐妹/兄弟): 待确认\n- 核心诉求与记录:\n")

    reg = load_registry()
    existing_child_session = None
    for entry in reg:
        if entry.get("bot_id") == bot_id:
            existing_child_session = entry.get("child_session_id")
        elif ilink_user_id and entry.get("ilink_user_id") == ilink_user_id and entry.get("status") == "active":
            entry["status"] = "expired"

    child_session_id = existing_child_session or create_child_session(bot_id, label)

    updated = False
    for entry in reg:
        if entry.get("bot_id") == bot_id:
            entry.update({
                "label": label,
                "bot_id": bot_id,
                "ilink_user_id": ilink_user_id,
                "child_session_id": child_session_id,
                "status": "active",
                "bound_at": int(time.time())
            })
            updated = True
            break
    if not updated:
        reg.append({
            "label": label,
            "bot_id": bot_id,
            "ilink_user_id": ilink_user_id,
            "child_session_id": child_session_id,
            "status": "active",
            "bound_at": int(time.time())
        })
    save_registry(reg)
    return {
        "ok": True,
        "status": "confirmed",
        "label": label,
        "bot_id": bot_id,
        "child_session_id": child_session_id
    }

def check_pending_qrs_once() -> list:
    """非阻塞检查 pending_qrs/ 下所有待扫码二维码的状态（供 poller.py 定时轮询顺带调用）"""
    if not os.path.exists(PENDING_QRS_DIR):
        return []
    now = int(time.time())
    confirmed_list = []
    for fn in sorted(os.listdir(PENDING_QRS_DIR)):
        if not fn.endswith(".json"):
            continue
        fpath = os.path.join(PENDING_QRS_DIR, fn)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                pending = json.load(f)
        except Exception:
            continue
        if now > pending.get("expires_at", 0):
            try:
                os.remove(fpath)
            except Exception:
                pass
            continue
        qr_tok = pending["qrcode"]
        label = pending.get("label") or "微信新用户"
        base_host = pending.get("base_host") or DEFAULT_BASE_URL
        q = urllib.parse.quote(qr_tok, safe="")
        url = f"{base_host.rstrip('/')}/ilink/bot/get_qrcode_status?qrcode={q}"
        try:
            res = http_get_json(url, timeout=3)
        except Exception:
            continue
        st = res.get("status")
        if st == "scaned_but_redirect":
            rhost = res.get("redirect_host")
            if rhost:
                pending["base_host"] = rhost if rhost.startswith("http") else f"https://{rhost}"
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(pending, f, ensure_ascii=False, indent=2)
        elif st == "confirmed":
            out = finalize_confirmed_bot(res, label, fallback_host=base_host)
            confirmed_list.append(out)
            try:
                os.remove(fpath)
            except Exception:
                pass
        elif st in ("expired", "verify_code_blocked"):
            try:
                os.remove(fpath)
            except Exception:
                pass
    return confirmed_list
def wait_for_scan(timeout_sec: int = 280) -> dict:
    if not os.path.exists(PENDING_QR_PATH):
        raise RuntimeError("没有找到 pending_qr.json，请先运行 --step qr 生成二维码")
    with open(PENDING_QR_PATH, "r", encoding="utf-8") as f:
        pending = json.load(f)

    qr_tok = pending["qrcode"]
    label = pending["label"]
    base_host = DEFAULT_BASE_URL
    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        q = urllib.parse.quote(qr_tok, safe="")
        url = f"{base_host.rstrip('/')}/ilink/bot/get_qrcode_status?qrcode={q}"
        try:
            res = http_get_json(url, timeout=38)
        except Exception:
            time.sleep(2)
            continue

        status = res.get("status")
        if status in ("wait", "scaned"):
            time.sleep(1)
            continue
        elif status == "scaned_but_redirect":
            rhost = res.get("redirect_host")
            if rhost:
                base_host = rhost if rhost.startswith("http") else f"https://{rhost}"
            continue
        elif status == "confirmed":
            out = finalize_confirmed_bot(res, label, fallback_host=base_host)
            try:
                os.remove(PENDING_QR_PATH)
            except Exception:
                pass
            return out
        elif status in ("expired", "verify_code_blocked"):
            return {"ok": False, "status": status, "message": "二维码已过期，请重新生成"}
        else:
            time.sleep(2)

    return {"ok": False, "status": "timeout", "message": "等待扫码超时"}

def main():
    parser = argparse.ArgumentParser(description="微信 ClawBot 新用户扫码接入器")
    parser.add_argument("--step", choices=["qr", "wait"], required=True)
    parser.add_argument("--label", default="微信用户", help="给该用户的备注标签")
    parser.add_argument("--qr-out", default="/workspace/files/wechat/qrcode.png", help="二维码图片输出路径")
    parser.add_argument("--timeout", type=int, default=280)
    args = parser.parse_args()

    if args.step == "qr":
        out = generate_qr(args.label, args.qr_out)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.step == "wait":
        out = wait_for_scan(timeout_sec=args.timeout)
        print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
