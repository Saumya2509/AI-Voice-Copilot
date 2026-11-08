"""Reply templates keyed by (event, language). No generated text: every reply comes from here.

`hi` is Devanagari for the hi-IN voice; `hinglish` is Roman Hindi with English dish names.
Optional language packs (mr, gu) fall back to Hinglish replies until they ship their own.
Keep every reply under 20 words.
"""
from __future__ import annotations

T: dict[str, dict[str, str]] = {
    "greeting": {
        "en": "Hello! What would you like to order today?",
        "hinglish": "Namaste! Bataiye, aaj kya order karenge?",
        "hi": "नमस्ते! बताइए, आज क्या ऑर्डर करेंगे?",
    },
    "added": {
        "en": "Added {items}. Anything else?",
        "hinglish": "{items} add kar diya. Aur kuch?",
        "hi": "{items} जोड़ दिया। और कुछ?",
    },
    "removed": {
        "en": "Removed {item}. Anything else?",
        "hinglish": "{item} hata diya. Aur kuch?",
        "hi": "{item} हटा दिया। और कुछ?",
    },
    "nothing_to_remove": {
        "en": "There is nothing on the order yet.",
        "hinglish": "Order mein abhi kuch nahi hai.",
        "hi": "ऑर्डर में अभी कुछ नहीं है।",
    },
    "modified": {
        "en": "Done, {item} {change}.",
        "hinglish": "Theek hai, {item} {change}.",
        "hi": "ठीक है, {item} {change}।",
    },
    "clarify_item": {
        "en": "Did you mean {options}?",
        "hinglish": "{options}, kaunsa chahiye?",
        "hi": "{options}, कौन सा चाहिए?",
    },
    "clarify_group": {
        "en": "{options} for the {item}?",
        "hinglish": "{item} {options}?",
        "hi": "{item} {options}?",
    },
    "clarify_again": {
        "en": "Sorry, which one: {options}?",
        "hinglish": "Maaf kijiye, kaunsa: {options}?",
        "hi": "माफ़ कीजिए, कौन सा: {options}?",
    },
    "not_understood_item": {
        "en": "Sorry, which dish was that? A curry, a bread or a rice dish?",
        "hinglish": "Maaf kijiye, kaunsi dish? Curry, roti ya rice?",
        "hi": "माफ़ कीजिए, कौन सी डिश? करी, रोटी या चावल?",
    },
    "modifier_problem": {
        "en": "{problem}",
        "hinglish": "{problem}",
        "hi": "{problem}",
    },
    "offer": {
        "en": "{item} goes well with that. Add one for ₹{price}?",
        "hinglish": "Iske saath {item} accha lagega. ₹{price} mein add karoon?",
        "hi": "इसके साथ {item} अच्छा लगेगा। ₹{price} में जोड़ दूँ?",
    },
    "offer_combo": {
        "en": "Add {item} and it becomes the {combo} combo for ₹{total}. Shall I?",
        "hinglish": "{item} add karne se {combo} combo ₹{total} ka ho jayega. Kar doon?",
        "hi": "{item} जोड़ने से {combo} कॉम्बो ₹{total} का हो जाएगा। कर दूँ?",
    },
    "offer_accepted": {
        "en": "Great, {item} added.",
        "hinglish": "Badhiya, {item} add kar diya.",
        "hi": "बढ़िया, {item} जोड़ दिया।",
    },
    "offer_declined": {
        "en": "No problem.",
        "hinglish": "Koi baat nahi.",
        "hi": "कोई बात नहीं।",
    },
    "readback": {
        "en": "That's {items}. Total ₹{total}. Shall I place the order?",
        "hinglish": "Aapka order: {items}. Total ₹{total}. Order place karoon?",
        "hi": "आपका ऑर्डर: {items}। कुल ₹{total}। ऑर्डर कर दूँ?",
    },
    "empty_cart": {
        "en": "Your order is empty. What would you like?",
        "hinglish": "Order abhi khaali hai. Kya lenge?",
        "hi": "ऑर्डर अभी खाली है। क्या लेंगे?",
    },
    "what_to_change": {
        "en": "Sure, what would you like to change?",
        "hinglish": "Zaroor, kya badalna hai?",
        "hi": "ज़रूर, क्या बदलना है?",
    },
    "ask_name": {
        "en": "May I have your name, please?",
        "hinglish": "Aapka naam bata dijiye?",
        "hi": "आपका नाम बता दीजिए?",
    },
    "ask_phone": {
        "en": "And your 10-digit phone number?",
        "hinglish": "Aur aapka 10 digit phone number?",
        "hi": "और आपका दस अंकों का फ़ोन नंबर?",
    },
    "phone_invalid": {
        "en": "Sorry, I need a 10-digit mobile number.",
        "hinglish": "Maaf kijiye, 10 digit ka mobile number chahiye.",
        "hi": "माफ़ कीजिए, दस अंकों का मोबाइल नंबर चाहिए।",
    },
    "placed": {
        "en": "Order placed. Your ticket number is {kot}. Thank you!",
        "hinglish": "Order place ho gaya. Ticket number {kot}. Dhanyavaad!",
        "hi": "ऑर्डर हो गया। टिकट नंबर {kot}। धन्यवाद!",
    },
    "pos_problem": {
        "en": "The order is saved but the kitchen system is not responding. Staff will confirm shortly.",
        "hinglish": "Order save ho gaya, kitchen system jawab nahi de raha. Staff abhi confirm karega.",
        "hi": "ऑर्डर सेव हो गया, किचन सिस्टम जवाब नहीं दे रहा। स्टाफ़ जल्द पुष्टि करेगा।",
    },
    "order_error": {
        "en": "Sorry, I couldn't place that: {reason}",
        "hinglish": "Maaf kijiye, order nahi ho paya: {reason}",
        "hi": "माफ़ कीजिए, ऑर्डर नहीं हो पाया: {reason}",
    },
    "price": {
        "en": "{item} is ₹{price}.",
        "hinglish": "{item} ₹{price} ka hai.",
        "hi": "{item} ₹{price} का है।",
    },
    "total": {
        "en": "Your total so far is ₹{total}.",
        "hinglish": "Abhi tak total ₹{total} hua.",
        "hi": "अभी तक कुल ₹{total} हुआ।",
    },
    "available": {
        "en": "Yes, {item} is available. Shall I add it?",
        "hinglish": "Haan, {item} available hai. Add karoon?",
        "hi": "हाँ, {item} मिलेगा। जोड़ दूँ?",
    },
    "unavailable": {
        "en": "Sorry, {item} is not available right now.",
        "hinglish": "Maaf kijiye, {item} abhi available nahi hai.",
        "hi": "माफ़ कीजिए, {item} अभी उपलब्ध नहीं है।",
    },
    "recommend": {
        "en": "You could try {item}, ₹{price}. Shall I add it?",
        "hinglish": "{item} try kijiye, ₹{price}. Add karoon?",
        "hi": "{item} आज़माइए, ₹{price}। जोड़ दूँ?",
    },
    "repeat": {
        "en": "So far: {items}. Total ₹{total}.",
        "hinglish": "Abhi tak: {items}. Total ₹{total}.",
        "hi": "अभी तक: {items}। कुल ₹{total}।",
    },
    "greet_back": {
        "en": "Hello! What can I get you?",
        "hinglish": "Namaste! Kya lenge?",
        "hi": "नमस्ते! क्या लेंगे?",
    },
    "cancelled": {
        "en": "Okay, I have cancelled the order. Thank you for calling.",
        "hinglish": "Theek hai, order cancel kar diya. Call karne ke liye shukriya.",
        "hi": "ठीक है, ऑर्डर रद्द कर दिया। कॉल करने के लिए शुक्रिया।",
    },
    "unknown": {
        "en": "Sorry, I didn't catch that. Could you say it again?",
        "hinglish": "Maaf kijiye, samajh nahi aaya. Phir se bolenge?",
        "hi": "माफ़ कीजिए, समझ नहीं आया। फिर से बोलेंगे?",
    },
    "unknown_typed": {
        "en": "Sorry, I still didn't get that. You can also type your order.",
        "hinglish": "Maaf kijiye, phir bhi samajh nahi aaya. Aap order type bhi kar sakte hain.",
        "hi": "माफ़ कीजिए, फिर भी समझ नहीं आया। आप ऑर्डर टाइप भी कर सकते हैं।",
    },
    "reprompt": {
        "en": "Are you still there? What else would you like?",
        "hinglish": "Aap line par hain? Aur kya lenge?",
        "hi": "आप लाइन पर हैं? और क्या लेंगे?",
    },
    "abandoned": {
        "en": "I can't hear you, so I'm ending the call. Please call again.",
        "hinglish": "Aawaz nahi aa rahi, call band kar raha hoon. Phir call kijiye.",
        "hi": "आवाज़ नहीं आ रही, कॉल बंद कर रहा हूँ। फिर कॉल कीजिए।",
    },
    "thanks_name": {
        "en": "Thanks, {name}. What would you like to order?",
        "hinglish": "Shukriya {name} ji. Kya order karenge?",
        "hi": "धन्यवाद {name} जी। क्या ऑर्डर करेंगे?",
    },
    "noted_phone": {
        "en": "Got your number. What would you like to order?",
        "hinglish": "Number note kar liya. Kya order karenge?",
        "hi": "नंबर नोट कर लिया। क्या ऑर्डर करेंगे?",
    },
    "added_short": {
        "en": "Added {items}.",
        "hinglish": "{items} add kar diya.",
        "hi": "{items} जोड़ दिया।",
    },
    "added_by_staff": {
        "en": "{item} added from the menu.",
        "hinglish": "{item} menu se add kiya.",
        "hi": "{item} मेनू से जोड़ा।",
    },
    "or": {"en": "or", "hinglish": "ya", "hi": "या"},
    "and": {"en": "and", "hinglish": "aur", "hi": "और"},
}

FALLBACK = {"mr": "hinglish", "gu": "hinglish"}


class Bi(str):
    """A reply in the call language that also carries its English rendering (`.en`), which is what the
    screen shows, and its Devanagari Hindi rendering (`.hi`), which is what the Hindi voice speaks for
    Hindi and Hinglish calls (Roman Hinglish read aloud by a Hindi voice sounds wrong). Joining and
    formatting keep all three in step."""

    en: str
    hi: str

    def __new__(cls, text: str, en: str | None = None, hi: str | None = None):
        obj = super().__new__(cls, text)
        obj.en = text if en is None else en
        obj.hi = text if hi is None else hi
        return obj


def en_of(value) -> str:
    return value.en if isinstance(value, Bi) else str(value)


def hi_of(value) -> str:
    return value.hi if isinstance(value, Bi) else str(value)


def bjoin(parts, sep: str = " ") -> Bi:
    parts = [p for p in parts if p]
    return Bi(sep.join(str(p) for p in parts), sep.join(en_of(p) for p in parts), sep.join(hi_of(p) for p in parts))


def say(key: str, lang: str, **values) -> Bi:
    table = T[key]
    lang = lang if lang in table else FALLBACK.get(lang, "en")
    text = table.get(lang, table["en"]).format(**values)
    english = table["en"].format(**{k: en_of(v) for k, v in values.items()})
    hindi = table.get("hi", table["en"]).format(**{k: hi_of(v) for k, v in values.items()})
    return Bi(text, english, hindi)


def join_options(labels: list[str], lang: str) -> Bi:
    return Bi(_join(labels, say("or", lang)), _join([en_of(x) for x in labels], "or"),
              _join([hi_of(x) for x in labels], T["or"]["hi"]))


def join_items(labels: list[str], lang: str) -> Bi:
    return Bi(_join(labels, say("and", lang)), _join([en_of(x) for x in labels], "and"),
              _join([hi_of(x) for x in labels], T["and"]["hi"]))


def _join(labels: list[str], word: str) -> str:
    if len(labels) <= 1:
        return "".join(labels)
    return ", ".join(labels[:-1]) + f" {word} " + labels[-1]
