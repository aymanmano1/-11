import logging
import os
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- الإعدادات والثوابت ---
# توكن بوت التليجرام الخاص بك (استبدله بالتوكن الحقيقي الخاص بك)
TELEGRAM_BOT_TOKEN = "7345647161:AAE1JFppa9exaLlQIAh-oaXmaNLdtO0NNSE"

# مفتاح Gemini API الخاص بك
# نصيحة: في بيئة الإنتاج، استخدم os.getenv("GEMINI_API_KEY") لتحميل المفتاح من متغيرات البيئة لأمان أفضل.
GEMINI_API_KEY = "AIzaSyAOL2PplFydnbXgb2faQ5eP8vYxz9GuGDE"

# تهيئة Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# قم بتهيئة التسجيل (Logging) لتتبع أحداث البوت
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# قائمة النماذج المدعومة التي يمكن للمستخدم الاختيار منها
# يمكنك إضافة نماذج Gemini أخرى هنا (مثل gemini-pro-vision إذا كنت تخطط للتعامل مع الصور)
AVAILABLE_GEMINI_MODELS = {
    "gemini-pro": "جيميناي برو (للنصوص)",
    "gemini-1.5-flash": "جيميناي 1.5 فلاش (سريع)"
}

# لتخزين النموذج المختار لكل مستخدم (مثال بسيط، في تطبيق أكبر استخدم قاعدة بيانات)
user_models = {}

# --- وظائف البوت ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يرسل رسالة ترحيب عندما يصدر المستخدم الأمر /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً بك يا {user.mention_html()}!\n"
        "أنا بوت تفاعلي مع نماذج جوجل جيميناي.\n"
        "يمكنك إرسال أي سؤال أو نص لي وسأقوم بالرد عليه.\n"
        "لاستعراض واختيار نموذج جيميناي، استخدم الأمر /select_model."
    )

async def select_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعرض للمستخدم خيارات لاختيار نموذج Gemini."""
    keyboard = []
    for model_name, model_description in AVAILABLE_GEMINI_MODELS.items():
        keyboard.append([InlineKeyboardButton(model_description, callback_data=model_name)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("الرجاء اختيار نموذج جيميناي:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يستجيب لضغطة زر اختيار النموذج."""
    query = update.callback_query
    await query.answer() # يجب استدعاء query.answer()

    selected_model = query.data
    user_id = query.from_user.id
    
    if selected_model in AVAILABLE_GEMINI_MODELS:
        user_models[user_id] = selected_model
        await query.edit_message_text(text=f"تم اختيار نموذج: {AVAILABLE_GEMINI_MODELS[selected_model]}.")
    else:
        await query.edit_message_text(text="اختيار نموذج غير صالح.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يتعامل مع الرسائل النصية من المستخدمين ويرسلها إلى Gemini."""
    user_message = update.message.text
    user_id = update.effective_user.id

    # الحصول على النموذج المختار للمستخدم، أو استخدام gemini-pro كافتراضي
    current_model = user_models.get(user_id, "gemini-pro")
    
    logger.info(f"المستخدم {user_id} أرسل: '{user_message}' باستخدام النموذج: {current_model}")

    try:
        # تهيئة النموذج المحدد
        model = genai.GenerativeModel(current_model)
        
        # إرسال الرسالة إلى نموذج Gemini
        response = model.generate_content(user_message)
        
        # إرسال رد Gemini إلى المستخدم
        await update.message.reply_text(response.text)
        
    except Exception as e:
        logger.error(f"حدث خطأ أثناء التفاعل مع Gemini: {e}")
        await update.message.reply_text(
            "عذراً، حدث خطأ أثناء محاولة التفاعل مع نموذج جيميناي. يرجى المحاولة مرة أخرى لاحقاً."
        )

def main() -> None:
    """يشغل البوت."""
    # قم بإنشاء كائن Application الخاص بالبوت الخاص بك
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("select_model", select_model))
    
    # إضافة معالج لاستقبال ضغطات الأزرار (لاختيار النموذج)
    application.add_handler(CallbackQueryHandler(button_callback))

    # إضافة معالج لجميع الرسائل النصية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ابدأ تشغيل البوت
    logger.info("بدء تشغيل البوت...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()