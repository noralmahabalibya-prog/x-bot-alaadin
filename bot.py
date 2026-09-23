"""Telegram assistant that drafts truthful X account appeals. Python 3.10+."""

import json
import logging
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}/"
APPEAL_URL = "https://help.x.com/en/forms/account-access/appeals"
COPYRIGHT_URL = "https://help.x.com/en/rules-and-policies/copyright-policy"
CHOICES = {
    "سبب غير معروف": "unknown",
    "اشتباه نشاط آلي": "automation",
    "حساب مخترق": "compromised",
    "حقوق نشر": "copyright",
    "سبب آخر": "other",
}
SESSIONS = {}  # In memory only; restarting the bot deletes the drafts.


def api(method, params):
    request = Request(API + method, data=urlencode(params).encode("utf-8"))
    with urlopen(request, timeout=40) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise ValueError(result.get("description", "Telegram API error"))
    return result["result"]


def send(chat_id, message, keyboard=None):
    params = {"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}
    if keyboard:
        params["reply_markup"] = json.dumps({"keyboard": [[x] for x in keyboard], "resize_keyboard": True}, ensure_ascii=False)
    else:
        params["reply_markup"] = json.dumps({"remove_keyboard": True})
    api("sendMessage", params)


def valid_handle(value):
    value = value.strip().removeprefix("@")
    if re.fullmatch(r"[A-Za-z0-9_]{1,15}", value):
        return "@" + value
    return None


def draft(handle, reason, detail):
    detail = " ".join(detail.split())
    introductions = {
        "unknown": "I am appealing the suspension of my account because I do not understand the reason for this action.",
        "automation": "I am requesting a review of the restriction placed on my account in connection with suspected automated activity.",
        "compromised": "I am requesting a review of my account restriction after noticing possible unauthorized access.",
        "copyright": "I am requesting clarification and a review of the action taken on my account regarding a copyright complaint.",
        "other": "I am requesting a review of the action taken on my account.",
    }
    return (
        f"Hello X Support,\n\nMy account is {handle}. {introductions[reason]}\n\n"
        f"Here is what happened, to the best of my knowledge: {detail}\n\n"
        "Please review my account and let me know what steps I can take to resolve this issue. "
        "Thank you."
    )


def handle_message(message):
    chat = message.get("chat", {})
    if chat.get("type") != "private" or not isinstance(message.get("text"), str):
        return
    chat_id = chat["id"]
    text = message["text"].strip()
    if text in ("/start", "/cancel", "إلغاء", "بدء طلب جديد"):
        SESSIONS.pop(chat_id, None)
        send(chat_id, "أهلًا! أساعدك تكتب استئنافًا لحساب X، لكن لا أستطيع استرجاعه بنفسي ولا أضمن قبول الطلب. لا ترسل كلمة السر أو رمز التحقق أو بيانات خاصة.\n\nأرسل يوزر حسابك في X، مثل @example")
        SESSIONS[chat_id] = {"step": "handle"}
        return
    state = SESSIONS.get(chat_id)
    if not state:
        send(chat_id, "للبدء أرسل /start")
        return
    if state["step"] == "handle":
        handle = valid_handle(text)
        if not handle:
            send(chat_id, "اكتب اليوزر فقط، مثل @example (حروف إنجليزية وأرقام وشرطة سفلية، بحد أقصى 15 حرفًا).")
            return
        state.update(handle=handle, step="reason")
        send(chat_id, "ما سبب إيقاف الحساب بحسب الإشعار الذي ظهر لك؟", list(CHOICES))
    elif state["step"] == "reason":
        if text not in CHOICES:
            send(chat_id, "اختر أحد الأسباب من الأزرار.", list(CHOICES))
            return
        state.update(reason=CHOICES[text], step="detail")
        extra = "\nإذا كان الموضوع حقوق نشر، لا تقدّم إشعارًا مضادًا إلا إذا كنت متأكدًا من صحة موقفك؛ له تبعات قانونية." if state["reason"] == "copyright" else ""
        send(chat_id, "احكِ باختصار ماذا حدث، ومتى عرفت بالإيقاف، وما الذي تريد من الدعم مراجعته. اكتب الحقائق فقط ولا ترسل كلمات مرور أو رموز تحقق أو بيانات شخصية." + extra)
    elif state["step"] == "detail":
        if len(text) < 15 or len(text) > 1200:
            send(chat_id, "اكتب وصفًا من 15 إلى 1200 حرف، بدون معلومات حساسة.")
            return
        if re.search(r"(?:password|كلمة\s*(?:المرور|السر)|رمز\s*التحقق|otp)\s*[:：=]", text, re.I):
            send(chat_id, "يبدو أن رسالتك تحتوي على بيانات دخول؛ رجاءً احذفها وأرسل وصفًا عامًا فقط.")
            return
        result = draft(state["handle"], state["reason"], text)
        SESSIONS.pop(chat_id, None)
        send(chat_id, "هذا نص مقترح بالإنجليزية؛ راجعه وعدّل أي شيء غير دقيق قبل إرساله:\n\n" + result)
        notice = "\n\nتنبيه: الإشعار المضاد لحقوق النشر إجراء قانوني مختلف، وليس النص أعلاه إشعارًا مضادًا. اقرأ سياسة X أولًا:\n" + COPYRIGHT_URL if state["reason"] == "copyright" else ""
        send(chat_id, "رابط الاستئناف الرسمي (افتحه وأنت مسجّل دخولك إلى الحساب الموقوف):\n" + APPEAL_URL + notice + "\n\nلصياغة نص جديد أرسل /start", ["بدء طلب جديد"])


def main():
    if not TOKEN:
        raise SystemExit("اضبط متغير TELEGRAM_BOT_TOKEN أولًا.")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    offset = None
    while True:
        try:
            params = {"timeout": 25, "allowed_updates": json.dumps(["message"])}
            if offset is not None:
                params["offset"] = offset
            for update in api("getUpdates", params):
                offset = update["update_id"] + 1
                try:
                    handle_message(update.get("message", {}))
                except (HTTPError, URLError, ValueError) as exc:
                    logging.warning("Could not process message: %s", type(exc).__name__)
        except (HTTPError, URLError, ValueError) as exc:
            logging.warning("Connection issue: %s", type(exc).__name__)
            time.sleep(5)


if __name__ == "__main__":
    main()
