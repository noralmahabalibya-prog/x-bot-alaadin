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
    "تهمة التزييف": "counterfeit",
    "تهمة حسابات غير موثوقة": "inauthentic",
    "تهمة حقوق النشر": "copyright",
    "سبب اخر": "other",
}
TEMPLATES = {
    "counterfeit": """إلى السيد/ة المسؤول/ة في فريق دعم العملاء في تويتر،

أتقدم بخالص اعتذاري عن أي إزعاج قد تسبب فيه حسابي الذي تم تعطيله عن طريق الخطأ. أرجو منكم أخذ هذه الرسالة بعين الاعتبار وإعادة النظر في قرار تعطيل الحساب الذي يحمل اسم المستخدم: [username@].

أود التأكيد على أنني لم أنتهك أي من شروط الاستخدام التابعة لخدمتكم، وأنني أقدر قواعد المجتمع وأتبعها بدقة. أعتقد بأن هذا الإجراء قد تم بشكل غير مبرر، وأنا على استعداد لتقديم أي معلومات إضافية قد تحتاجونها لإثبات هويتي ونزاهة استخدام الحساب.

أتمنى من فضلكم إعادة تفعيل حسابي في أسرع وقت ممكن، حيث أعتبر حسابي وسيلة مهمة للتواصل مع العائلة والأصدقاء ولأغراض عملي.

أشكركم على تعاونكم وفهمكم، وأتطلع لاستعادة حسابي قريبًا.""",
    "inauthentic": """مرحبًا فريق دعم X، أتقدم بطلب لإعادة النظر في إيقاف حسابي @username، وأرجو إحالة هذا الالتماس إلى أحد المختصين لإجراء مراجعة بشرية للحساب والسبب الذي استند إليه القرار.

أطلب توضيح المخالفة المحددة والمحتوى المرتبط بها، حتى أتمكن من تقديم رد دقيق ومعالجة أي مشكلة.

ألتزم باحترام قواعد X، وأنا مستعد لاتخاذ الخطوات المطلوبة لتصحيح أي مخالفة تثبت بعد المراجعة.

يرجى إعادة تفعيل الحساب إذا تبيّن أن الإيقاف وقع بالخطأ، وإبلاغي بنتيجة المراجعة وأسبابها عبر البريد الإلكتروني المرتبط بالحساب.

شكرًا لوقتكم ومساعدتكم.""",
    "copyright": """Hello dear Twitter team, my account has been suspended ( @username ) due to violation of rights, and after filing DMCA a counter-report, I received a response from you, returning the account within 10 days, 
‎‏It's been 9 months and I haven't received a response. Please reactivate my account and thank you""",
    "other": """Hello Twitter Support Team, I am submitting an appeal against the suspension of my account on charges of impersonation. I would like to clarify that I did not impersonate anyone, and this is a mistake on your part or on the part of the automated systems. Please reconsider the suspension of my account, please, as it is very important to me and I love this platform very much. With sincere respect and greetings.""",
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


def draft(handle, reason):
    # Replace only the placeholder; preserve all other characters verbatim.
    username = handle.removeprefix("@")
    return TEMPLATES[reason].replace("username", username)


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
        result = draft(state["handle"], CHOICES[text])
        send(chat_id, result, list(CHOICES))


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
