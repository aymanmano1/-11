import logging
import os
import google.genai as genai
from google.genai import types
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import mimetypes
import uuid
import asyncio # لاستخدام sleep إذا احتجنا لتأخير

# --- الإعدادات والثوابت ---
# توكن بوت التليجرام الخاص بك (تم تحديثه بناءً على ما قدمته)
TELEGRAM_BOT_TOKEN = "7345647161:AAE1JFppa9exaLlQIAh-oaXmaNLdtO0NNSE"

# مفتاح Gemini API الخاص بك
# نصيحة: في بيئة الإنتاج، استخدم os.getenv("GEMINI_API_KEY") لتحميل المفتاح من متغيرات البيئة لأمان أفضل.
GEMINI_API_KEY = "AIzaSyAOL2PplFydnbXgb2faQ5eP8vYxz9GuGDE"

# تهيئة Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# النموذج الذي سيتفاعل معه البوت لتوليد الصور
IMAGE_GENERATION_MODEL = "gemini-2.0-flash-preview-image-generation"

# تهيئة التسجيل (Logging) لتتبع أحداث البوت
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING) # لتقليل رسائل التحذير من مكتبة httpx
logger = logging.getLogger(__name__)

# مسار لتخزين الصور المؤقتة التي تم إنشاؤها
TEMP_IMAGE_DIR = "generated_images"
if not os.path.exists(TEMP_IMAGE_DIR):
    os.makedirs(TEMP_IMAGE_DIR)

# --- وظائف مساعدة ---
def save_binary_file_to_temp(data, mime_type):
    """
    يحفظ البيانات الثنائية (صورة) إلى ملف مؤقت في مجلد الصور المؤقتة.
    يعيد اسم المسار الكامل للملف المحفوظ.
    """
    file_extension = mimetypes.guess_extension(mime_type)
    if not file_extension:
        file_extension = ".png" # افتراضي إذا لم يتم استنتاج الامتداد
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    full_path = os.path.join(TEMP_IMAGE_DIR, unique_filename)
    
    try:
        with open(full_path, "wb") as f:
            f.write(data)
        logger.info(f"تم حفظ الملف مؤقتاً: {full_path}")
        return full_path
    except Exception as e:
        logger.error(f"فشل في حفظ الملف: {e}")
        return None

# --- وظائف البوت ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يرسل رسالة ترحيب عندما يصدر المستخدم الأمر /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً بك يا {user.mention_html()}!\n"
        "أنا بوت لتوليد الصور باستخدام نموذج جوجل جيميناي.\n"
        "لإنشاء صورة، استخدم الأمر: `/صورة [وصف الصورة]` أو `/imagine [وصف الصورة]`.\n"
        "مثال: `/صورة قطة لطيفة تلعب بكرة صوف`"
    )

async def imagine_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يتعامل مع الأمر /imagine أو /صورة لإنشاء الصور."""
    # الوصف يأتي بعد الأمر، ندمج كل الكلمات
    prompt = " ".join(context.args) 
    user_id = update.effective_user.id

    if not prompt:
        await update.message.reply_text("الرجاء تقديم وصف للصورة.\nمثال: `/صورة كلب يطير في الفضاء`")
        return

    # إرسال رسالة "جاري العمل" للمستخدم
    thinking_message = await update.message.reply_text(f"جاري إنشاء صورة لـ: \"{prompt}\"...\nهذا قد يستغرق بعض الوقت.")
    logger.info(f"المستخدم {user_id} طلب صورة: '{prompt}'")

    image_path = None
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            response_mime_type="text/plain",
        )

        # دفق المحتوى من Gemini
        for chunk in client.models.generate_content_stream(
            model=IMAGE_GENERATION_MODEL,
            contents=contents,
            config=generate_content_config,
        ):
            # التأكد من أن التقطيع يحتوي على بيانات صالحة
            if (
                chunk.candidates
                and chunk.candidates[0].content
                and chunk.candidates[0].content.parts
                and chunk.candidates[0].content.parts[0].inline_data
                and chunk.candidates[0].content.parts[0].inline_data.data
            ):
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                data_buffer = inline_data.data
                mime_type = inline_data.mime_type
                
                # حفظ الصورة مؤقتًا
                image_path = save_binary_file_to_temp(data_buffer, mime_type)
                if image_path:
                    # إرسال الصورة للمستخدم
                    await update.message.reply_photo(photo=open(image_path, 'rb'))
                    logger.info(f"تم إرسال الصورة للمستخدم {user_id}")
                    break # الخروج من الحلقة بعد الحصول على أول جزء من الصورة
            else:
                # هذا الجزء قد يتعامل مع رسائل نصية أو أخطاء من API
                if chunk.text:
                    logger.warning(f"تم استلام جزء نصي من Gemini: {chunk.text}")
        
        if not image_path:
            await update.message.reply_text("عذراً، لم أتمكن من إنشاء الصورة بالوصف المطلوب. قد يكون الوصف غير واضح أو غير مناسب.")

    except Exception as e:
        logger.error(f"حدث خطأ أثناء توليد الصورة: {e}", exc_info=True) # exc_info=True لطبع تتبع الخطأ كاملاً
        await update.message.reply_text(
            "عذراً، حدث خطأ أثناء محاولة إنشاء الصورة. يرجى التأكد من أن الوصف واضح وصالح."
        )
    finally:
        # حذف رسالة "جاري العمل"
        if thinking_message:
            try:
                await thinking_message.delete()
            except Exception as e:
                logger.warning(f"فشل في حذف رسالة جاري العمل: {e}")

        # حذف الملف المؤقت بعد إرساله
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            logger.info(f"تم حذف الملف المؤقت: {image_path}")


def main() -> None:
    """يشغل البوت."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # إضافة معالج لأمر /start
    application.add_handler(CommandHandler("start", start))
    
    # إضافة معالج لأمر /imagine و /صورة
    application.add_handler(CommandHandler("imagine", imagine_command))
    application.add_handler(CommandHandler("صورة", imagine_command)) # لدعم الأمر بالعربية

    # ابدأ تشغيل البوت
    logger.info("بدء تشغيل البوت...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
