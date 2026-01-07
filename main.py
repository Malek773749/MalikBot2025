#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MalikBot2025 Pro - النسخة المحسنة المطورة
نظام نقاط متكامل مع PDF، ذكاء اصطناعي، إحالة متعددة المستويات
"""

import telebot
import sqlite3
import os
import logging
import datetime
import atexit
import time
import hashlib
import threading
import random
import string
import traceback
import shutil
import gzip
import signal
import sys
import re
import json
import base64
from telebot import types
from fpdf import FPDF
from cryptography.fernet import Fernet

# ===== إعدادات مدمجة في الكود (سيتم تعبئتها يدوياً) =====
BOT_TOKEN = ""  # ⚠️ ضع توكن البوت هنا (من @BotFather)
ADMIN_ID =   # ⚠️ ضع معرف المشرف هنا
CHANNEL = ""  # ⚠️ ضع معرف القناة هنا
OPENAI_KEY = ""  # ⚠️ (اختياري) ضع مفتاح OpenAI API هنا

# ===== توليد مفتاح تشفير تلقائي =====
def generate_encryption_key():
    """توليد مفتاح تشفير عشوائي"""
    key = Fernet.generate_key()
    return key.decode()

ENCRYPTION_KEY = generate_encryption_key()

# ===== إعدادات النظام =====
DB_FILE = "malikbot.db"
LOG_FILE = "malikbot.log"
BACKUP_DIR = "backups"
MAX_PDF_SIZE = 10000
MAX_AI_PROMPT = 1000
DAILY_AI_LIMIT = 3
SESSION_TIMEOUT = 1800
BACKUP_RETENTION_DAYS = 7

# ===== أسعار الخدمات (نقاط) =====
POINTS_CONFIG = {
    'join_bonus': 1.0,
    'referral_bonus': 1.0,
    'ad_bonus': 1.0,
    'ai_cost': 0.30,
    'pdf_cost': 0.30,
    'min_withdraw': 50.0,
    'withdraw_fee': 2.0,
}

# ===== حدود النقاط =====
POINTS_LIMITS = {
    'daily_ads': 10,
    'daily_ai_free': 3,
    'max_daily_points': 100,
    'max_weekly_points': 500,
}

# ===== تهيئة البوت =====
bot = telebot.TeleBot(BOT_TOKEN)

# ===== نظام التشفير =====
class EncryptionManager:
    def __init__(self, key):
        key_bytes = key.encode()[:32].ljust(32, b'\0')
        self.cipher = Fernet(base64.urlsafe_b64encode(key_bytes))

    def encrypt(self, data):
        """تشفير البيانات"""
        try:
            if isinstance(data, str):
                data = data.encode()
            return self.cipher.encrypt(data).decode()
        except Exception:
            return data if isinstance(data, str) else data.decode() if isinstance(data, bytes) else str(data)

    def decrypt(self, data):
        """فك تشفير البيانات"""
        try:
            if isinstance(data, str):
                data = data.encode()
            return self.cipher.decrypt(data).decode()
        except Exception:
            return data if isinstance(data, str) else data.decode() if isinstance(data, bytes) else str(data)

# تهيئة مدير التشفير
encryptor = EncryptionManager(ENCRYPTION_KEY)

# ===== إعدادات التسجيل =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ])
logger = logging.getLogger(__name__)

# ===== نظام معالجة الأخطاء =====
def error_handler(func):
    """مصحح الأخطاء"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}\n{traceback.format_exc()}")
            try:
                if args and hasattr(args[0], 'chat'):
                    msg = args[0]
                    bot.send_message(msg.chat.id, "❌ حدث خطأ غير متوقع. يرجى المحاولة لاحقاً.")
            except:
                pass
            return None
    return wrapper

# ===== نظام إدارة قاعدة البيانات =====
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """الحصول على اتصال قاعدة البيانات"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_db_cursor():
    """الحصول على مؤشر قاعدة البيانات"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

# ===== تهيئة قاعدة البيانات =====
def init_database():
    """تهيئة قاعدة البيانات مع الجداول اللازمة"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                lang TEXT DEFAULT 'ar',
                points REAL DEFAULT 0.0,
                ref_code TEXT UNIQUE,
                ref_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                last_active TEXT DEFAULT (datetime('now')),
                daily_ads INTEGER DEFAULT 0,
                daily_ai INTEGER DEFAULT 0,
                total_refs INTEGER DEFAULT 0,
                total_earned REAL DEFAULT 0.0,
                daily_reset TEXT DEFAULT (datetime('now')),
                weekly_reset TEXT DEFAULT (datetime('now'))
            )""")

            cursor.execute("""CREATE TABLE IF NOT EXISTS referrals(
                ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                bonus_paid BOOLEAN DEFAULT FALSE,
                created_at TEXT DEFAULT (datetime('now'))
            )""")

            cursor.execute("""CREATE TABLE IF NOT EXISTS transactions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                description TEXT,
                status TEXT DEFAULT 'completed',
                created_at TEXT DEFAULT (datetime('now'))
            )""")

            cursor.execute("""CREATE TABLE IF NOT EXISTS ai_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prompt TEXT,
                response TEXT,
                tokens INTEGER,
                cost REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )""")

            cursor.execute("""CREATE TABLE IF NOT EXISTS pdf_files(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT,
                file_size INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )""")

            cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )""")

            cursor.execute("""CREATE TABLE IF NOT EXISTS admin_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )""")

            cursor.execute("""CREATE TABLE IF NOT EXISTS withdrawals(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                method TEXT,
                info TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                processed_at TEXT
            )""")

            # إضافة الإعدادات الافتراضية فقط إذا لم تكن موجودة
            cursor.execute("SELECT COUNT(*) FROM settings")
            if cursor.fetchone()[0] == 0:
                default_settings = [
                    ('maintenance_mode', 'off'),
                    ('points_enabled', 'on'),
                    ('welcome_message', '🎉 مرحباً بك في MalikBot2025 Pro!'),
                    ('ad_message', '📺 شاهد هذا الإعلان لمدة 30 ثانية لتحصل على نقطة!'),
                    ('currency_name', 'نقطة'),
                    ('admin_notifications', 'true'),
                    ('backup_interval', '24'),
                    ('withdraw_methods', 'paypal,wallet,bank'),
                    ('referral_levels', '3'),
                    ('level2_bonus', '0.5'),
                    ('level3_bonus', '0.25'),
                    ('daily_ad_limit', '10'),
                    ('daily_ai_limit', '3'),
                    ('max_pdf_size', '10000'),
                    ('max_ai_length', '1000'),
                    ('ad_duration', '30'),
                    ('min_withdraw', '50'),
                    ('withdraw_fee', '2'),
                    ('auto_backup', 'true'),
                    ('channel_check', 'false')
                ]

                for key, value in default_settings:
                    cursor.execute(
                        "INSERT INTO settings(key, value, updated_at) VALUES(?, ?, datetime('now'))",
                        (key, value))
                logger.info("✅ تم إضافة الإعدادات الافتراضية")

        logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تهيئة قاعدة البيانات: {e}")
        # محاولة إنشاء قاعدة بيانات بسيطة
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, points REAL DEFAULT 0)")
            conn.commit()
            conn.close()
            logger.info("✅ تم إنشاء قاعدة بيانات أساسية")
            return True
        except Exception as e2:
            logger.error(f"❌ فشل إنشاء قاعدة بيانات أساسية: {e2}")
            return False

# ===== دوال مساعدة =====
def get_setting(key, default=''):
    """الحصول على إعداد من قاعدة البيانات"""
    try:
        with get_db_cursor() as cursor:
            # التحقق أولاً من وجود جدول settings
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            if not cursor.fetchone():
                # إنشاء الجدول إذا لم يكن موجوداً
                cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                )""")
                # إضافة بعض الإعدادات الأساسية
                cursor.execute("INSERT INTO settings(key, value) VALUES('maintenance_mode', 'off')")
                cursor.execute("INSERT INTO settings(key, value) VALUES('currency_name', 'نقطة')")
                cursor.execute("INSERT INTO settings(key, value) VALUES('welcome_message', '🎉 مرحباً بك في MalikBot2025 Pro!')")
                logger.info("✅ تم إنشاء جدول settings تلقائياً")
            
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else default
    except Exception as e:
        logger.error(f"خطأ في get_setting: {e}")
        return default

def update_setting(key, value):
    """تحديث إعداد في قاعدة البيانات"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO settings(key, value, updated_at)
                VALUES(?, ?, datetime('now'))
            """, (key, value))
        return True
    except Exception as e:
        logger.error(f"خطأ في update_setting: {e}")
        return False

def get_user_language(user_id):
    """الحصول على لغة المستخدم"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 'ar'
    except Exception as e:
        logger.error(f"خطأ في get_user_language: {e}")
        return 'ar'

def get_user_points(user_id):
    """الحصول على نقاط المستخدم"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return float(result[0]) if result else 0.0
    except Exception as e:
        logger.error(f"خطأ في get_user_points: {e}")
        return 0.0

def update_user_points(user_id, points, reason=''):
    """تحديث نقاط المستخدم"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, user_id))
            cursor.execute("UPDATE users SET last_active = datetime('now') WHERE user_id = ?", (user_id,))
            cursor.execute(
                "INSERT INTO transactions(user_id, amount, type, description) VALUES(?, ?, ?, ?)",
                (user_id, points, 'points_update', reason))

            if points > 0:
                cursor.execute("UPDATE users SET total_earned = total_earned + ? WHERE user_id = ?", (points, user_id))

        logger.debug(f"تم تحديث نقاط المستخدم {user_id} بمقدار {points} ({reason})")
        return True
    except Exception as e:
        logger.error(f"خطأ في update_user_points: {e}")
        return False

def reset_daily_counts():
    """إعادة تعيين العدادات اليومية"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE users SET daily_ads = 0, daily_ai = 0 WHERE DATE(daily_reset) < DATE('now')")
            cursor.execute("UPDATE users SET daily_reset = datetime('now') WHERE DATE(daily_reset) < DATE('now')")
            cursor.execute("UPDATE users SET weekly_reset = datetime('now') WHERE DATE(weekly_reset, '+7 days') < DATE('now')")
        return True
    except Exception as e:
        logger.error(f"خطأ في reset_daily_counts: {e}")
        return False

def generate_referral_code(user_id):
    """توليد كود إحالة فريد"""
    try:
        timestamp = str(int(time.time() * 1000))
        seed = f"{user_id}{timestamp}{random.randint(1000, 9999)}"
        code = hashlib.md5(seed.encode()).hexdigest()[:8].upper()

        with get_db_cursor() as cursor:
            cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (code,))
            while cursor.fetchone():
                seed = f"{user_id}{timestamp}{random.randint(1000, 9999)}"
                code = hashlib.md5(seed.encode()).hexdigest()[:8].upper()
                cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (code,))

        return f"REF{code}"
    except Exception as e:
        logger.error(f"خطأ في generate_referral_code: {e}")
        return f"REF{user_id}{int(time.time())}"

def register_user(message):
    """تسجيل مستخدم جديد"""
    user_id = message.chat.id
    first_name = message.from_user.first_name or ""
    username = message.from_user.username or ""

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))

            if not cursor.fetchone():
                referral_code = generate_referral_code(user_id)
                referred_by = None

                if len(message.text.split()) > 1:
                    ref_code = message.text.split()[1]
                    cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
                    referrer = cursor.fetchone()
                    if referrer and referrer['user_id'] != user_id:
                        referred_by = referrer['user_id']

                join_bonus = POINTS_CONFIG['join_bonus']

                cursor.execute(
                    "INSERT INTO users(user_id, first_name, username, ref_code, ref_by, points, total_earned) VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (user_id, first_name, username, referral_code, referred_by, join_bonus, join_bonus))

                cursor.execute(
                    "INSERT INTO transactions(user_id, amount, type, description) VALUES(?, ?, ?, ?)",
                    (user_id, join_bonus, 'join_bonus', 'مكافأة انضمام'))

                if referred_by:
                    cursor.execute("INSERT INTO referrals(referrer_id, referred_id) VALUES(?, ?)", (referred_by, user_id))

                    ref_bonus = POINTS_CONFIG['referral_bonus']
                    cursor.execute("UPDATE users SET points = points + ?, total_refs = total_refs + 1 WHERE user_id = ?", (ref_bonus, referred_by))

                    cursor.execute(
                        "INSERT INTO transactions(user_id, amount, type, description) VALUES(?, ?, ?, ?)",
                        (referred_by, ref_bonus, 'referral_bonus', f'إحالة المستخدم {user_id}'))

                    cursor.execute("UPDATE referrals SET bonus_paid = TRUE WHERE referrer_id = ? AND referred_id = ?", (referred_by, user_id))

                logger.info(f"✅ تم تسجيل مستخدم جديد: {user_id} - {first_name}")
                return True, "تم التسجيل بنجاح"
            else:
                cursor.execute(
                    "UPDATE users SET first_name = ?, username = ?, last_active = datetime('now') WHERE user_id = ?",
                    (first_name, username, user_id))
                logger.debug(f"تم تحديث بيانات المستخدم: {user_id}")
                return False, "مستخدم مسجل مسبقاً"
    except Exception as e:
        logger.error(f"خطأ في register_user: {e}")
        return False, f"خطأ في التسجيل: {e}"

def is_subscribed(user_id):
    """التحقق من اشتراك المستخدم في القناة"""
    return True  # تم تعطيل مؤقتاً

# ===== نصوص مترجمة =====
TEXTS = {
    'ar': {
        'welcome': '🎉 مرحبًا بك في MalikBot2025 Pro!\n\n',
        'menu': '📱 **القائمة الرئيسية:**',
        'earn_points': '💰 ربح النقاط',
        'create_pdf': '📄 إنشاء PDF',
        'ai_assistant': '🤖 الذكاء الاصطناعي',
        'control_panel': '📊 لوحة التحكم',
        'my_account': '👤 حسابي',
        'referral': '👥 نظام الإحالة',
        'withdraw': '💳 سحب النقاط',
        'help': '❓ المساعدة',
        'points_balance': '💳 نقاطك: {points}',
        'admin_only': '🚫 هذا الأمر للمشرف فقط!',
        'not_subscribed': '⚠️ يجب الاشتراك في القناة أولاً:\n{channel}',
        'maintenance': '🔧 البوت قيد الصيانة. الرجاء المحاولة لاحقاً.',
        'pdf_created': '✅ تم إنشاء PDF بنجاح!',
        'ai_thinking': '🤔 جاري التفكير...',
        'ai_error': '❌ حدث خطأ في الذكاء الاصطناعي.',
        'ai_no_key': '❌ لم يتم تكوين مفتاح OpenAI. الرجاء إضافته في Railway Variables.',
        'ai_quota_exceeded': '❌ تجاوزت الحد المسموح. الرجاء تحديث المفتاح.',
        'ai_rate_limit': '❌ تجاوزت الحد المسموح للطلبات. حاول بعد دقائق.',
        'insufficient_points': '❌ نقاطك غير كافية. تحتاج إلى {points} نقطة.',
        'ad_watched': '✅ شكراً لمشاهدة الإعلان! حصلت على {points} نقطة.',
        'withdraw_request': '📤 تم تقديم طلب السحب بنجاح.',
        'referral_link': '🔗 رابط الإحالة الخاص بك:',
        'subscribe_btn': '📢 اشترك في القناة',
        'check_sub_btn': '✅ تحقق من الاشتراك',
        'back_btn': '🔙 رجوع',
        'too_long': '❌ النص طويل جداً. الحد الأقصى {length} حرف.',
        'invalid_format': '❌ تنسيق غير صحيح.',
        'withdraw_info_required': '📝 يرجى إرسال معلومات {method} الخاصة بك:',
        'withdraw_info_invalid': '❌ معلومات السحب غير صالحة.',
        'backup_created': '💾 تم إنشاء نسخة احتياطية بنجاح.',
        'stats_updated': '📊 تم تحديث الإحصائيات.',
        'user_not_found': '❌ المستخدم غير موجود.',
        'operation_success': '✅ تمت العملية بنجاح.',
        'operation_failed': '❌ فشلت العملية.',
        'daily_limit_reached': '⚠️ لقد وصلت إلى الحد اليومي. حاول غداً.',
        'file_too_large': '📁 الملف كبير جداً. الحد الأقصى {max_size} بايت.',
        'invalid_input': '❌ مدخلات غير صالحة.',
        'processing': '⏳ جاري المعالجة...',
        'confirm_action': '✅ هل تريد تأكيد هذا الإجراء؟',
        'action_cancelled': '❌ تم إلغاء الإجراء.',
        'feature_coming_soon': '🚧 هذه الميزة قيد التطوير.',
        'bot_updated': '🔄 تم تحديث البوت.',
        'server_status': '📊 حالة الخدمة: {status}',
        'connection_error': '🔌 خطأ في الاتصال.',
        'account_verified': '✅ تم التحقق من الحساب.',
        'account_suspended': '🚫 حساب معطل.',
        'contact_admin': '📞 يرجى التواصل مع المشرف.',
    },
    'en': {
        'welcome': '🎉 Welcome to MalikBot2025 Pro!\n\n',
        'menu': '📱 **Main Menu:**',
        'earn_points': '💰 Earn Points',
        'create_pdf': '📄 Create PDF',
        'ai_assistant': '🤖 AI Assistant',
        'control_panel': '📊 Control Panel',
        'my_account': '👤 My Account',
        'referral': '👥 Referral System',
        'withdraw': '💳 Withdraw Points',
        'help': '❓ Help',
        'points_balance': '💳 Your Points: {points}',
        'admin_only': '🚫 This command is for admin only!',
        'not_subscribed': '⚠️ You must subscribe to the channel first:\n{channel}',
        'maintenance': '🔧 Bot is under maintenance.',
        'pdf_created': '✅ PDF created successfully!',
        'ai_thinking': '🤔 Thinking...',
        'ai_error': '❌ Error in AI service.',
        'ai_no_key': '❌ OpenAI API key not configured. Please add it in Railway Variables.',
        'ai_quota_exceeded': '❌ Quota exceeded. Please update your API key.',
        'ai_rate_limit': '❌ Rate limit exceeded. Try again in a few minutes.',
        'insufficient_points': '❌ Insufficient points. You need {points} points.',
        'ad_watched': '✅ Thanks for watching the ad! You earned {points} points.',
        'withdraw_request': '📤 Withdrawal request submitted successfully.',
        'referral_link': '🔗 Your referral link:',
        'subscribe_btn': '📢 Join Channel',
        'check_sub_btn': '✅ Check Subscription',
        'back_btn': '🔙 Back',
        'too_long': '❌ Text is too long. Maximum {length} characters.',
        'invalid_format': '❌ Invalid format.',
        'withdraw_info_required': '📝 Please send your {method} information:',
        'withdraw_info_invalid': '❌ Invalid withdrawal information.',
        'backup_created': '💾 Backup created successfully.',
        'stats_updated': '📊 Statistics updated.',
        'user_not_found': '❌ User not found.',
        'operation_success': '✅ Operation completed successfully.',
        'operation_failed': '❌ Operation failed.',
        'daily_limit_reached': '⚠️ Daily limit reached. Try again tomorrow.',
        'file_too_large': '📁 File is too large. Maximum {max_size} bytes.',
        'invalid_input': '❌ Invalid input.',
        'processing': '⏳ Processing...',
        'confirm_action': '✅ Do you want to confirm this action?',
        'action_cancelled': '❌ Action cancelled.',
        'feature_coming_soon': '🚧 This feature is under development.',
        'bot_updated': '🔄 Bot updated.',
        'server_status': '📊 Server status: {status}',
        'connection_error': '🔌 Connection error.',
        'account_verified': '✅ Account verified.',
        'account_suspended': '🚫 Account suspended.',
        'contact_admin': '📞 Please contact admin.',
    }
}

def get_text(key, user_id=None, **kwargs):
    """الحصول على نص مترجم"""
    lang = get_user_language(user_id) if user_id else 'ar'
    text = TEXTS.get(lang, {}).get(key, TEXTS['ar'].get(key, key))
    if kwargs and isinstance(text, str):
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

# ===== معالجة الأوامر =====
@bot.message_handler(commands=['start'])
@error_handler
def start_command(message):
    """معالجة أمر /start"""
    user_id = message.chat.id

    if get_setting('maintenance_mode', 'off').lower() == 'on' and user_id != ADMIN_ID:
        bot.send_message(user_id, get_text('maintenance', user_id))
        return

    is_new, msg = register_user(message)

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT ref_code FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            referral_code = user_data['ref_code'] if user_data else ""
    except:
        referral_code = ""

    referral_link = f"https://t.me/{bot.get_me().username}?start={referral_code}"

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        get_text('earn_points', user_id),
        get_text('create_pdf', user_id),
        get_text('ai_assistant', user_id),
        get_text('my_account', user_id),
        get_text('referral', user_id),
        get_text('withdraw', user_id),
        get_text('help', user_id)
    ]

    if user_id == ADMIN_ID:
        buttons.append(get_text('control_panel', user_id))

    keyboard.add(*buttons)

    welcome_msg = get_text('welcome', user_id) + get_setting('welcome_message', '')
    if is_new:
        welcome_msg += "\n\n🎁 **مكافأة ترحيبية: 1 نقطة!**"

    welcome_msg += f"\n\n{get_text('referral_link', user_id)}\n`{referral_link}`"
    welcome_msg += f"\n\n{get_text('points_balance', user_id, points=get_user_points(user_id))}"

    bot.send_message(user_id, welcome_msg, reply_markup=keyboard, parse_mode='Markdown')
    bot.send_message(user_id, get_text('menu', user_id), parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
@error_handler
def check_subscription_callback(call):
    """التحقق من الاشتراك"""
    user_id = call.message.chat.id

    if is_subscribed(user_id):
        bot.delete_message(user_id, call.message.message_id)
        start_command(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد في القناة!", show_alert=True)

# ===== ربح النقاط =====
@bot.message_handler(func=lambda m: m.text in [get_text('earn_points', m.chat.id), "💰 ربح النقاط"])
@error_handler
def earn_points_command(message):
    """معالجة طلب ربح النقاط"""
    user_id = message.chat.id

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT daily_ads FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            daily_ads = result['daily_ads'] if result else 0
    except:
        daily_ads = 0

    daily_limit = int(get_setting('daily_ad_limit', '10'))

    if daily_ads >= daily_limit:
        bot.send_message(user_id, get_text('daily_limit_reached', user_id))
        return

    ad_duration = int(get_setting('ad_duration', '30'))
    ad_bonus = POINTS_CONFIG['ad_bonus']

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(f"▶️ مشاهدة الإعلان ({ad_duration} ثانية)", callback_data="watch_ad"),
        types.InlineKeyboardButton("⏸️ تخطي", callback_data="skip_ad"))

    ad_message = get_setting('ad_message', '📺 شاهد هذا الإعلان!')

    bot.send_message(
        user_id,
        f"{ad_message}\n\n"
        f"💰 المكافأة: {ad_bonus} {get_setting('currency_name', 'نقطة')}\n"
        f"⏱️ المدة: {ad_duration} ثانية\n"
        f"📊 اليوم: {daily_ads}/{daily_limit}",
        reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data in ["watch_ad", "skip_ad"])
@error_handler
def handle_ad_callback(call):
    """معالجة مشاهدة الإعلان"""
    user_id = call.message.chat.id

    if call.data == "watch_ad":
        bot.answer_callback_query(call.id, "⏳ جاري تشغيل الإعلان...")
        time.sleep(2)

        try:
            with get_db_cursor() as cursor:
                cursor.execute("UPDATE users SET daily_ads = daily_ads + 1 WHERE user_id = ?", (user_id,))
        except:
            pass

        ad_bonus = POINTS_CONFIG['ad_bonus']
        update_user_points(user_id, ad_bonus, 'مكافأة مشاهدة إعلان')

        bot.edit_message_text(
            get_text('ad_watched', user_id, points=ad_bonus) + "\n\n" +
            get_text('points_balance', user_id, points=get_user_points(user_id)),
            user_id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "تم تخطي الإعلان")
        bot.delete_message(user_id, call.message.message_id)

# ===== إنشاء PDF =====
@bot.message_handler(func=lambda m: m.text in [get_text('create_pdf', m.chat.id), "📄 إنشاء PDF"])
@error_handler
def create_pdf_command(message):
    """معالجة طلب إنشاء PDF"""
    user_id = message.chat.id
    pdf_cost = POINTS_CONFIG['pdf_cost']

    if get_user_points(user_id) < pdf_cost:
        bot.send_message(user_id, get_text('insufficient_points', user_id, points=pdf_cost))
        return

    max_pdf_size = int(get_setting('max_pdf_size', '10000'))

    bot.send_message(
        user_id,
        f"📝 **إنشاء مستند PDF**\n\n"
        f"أرسل النص الذي تريد تحويله إلى PDF (الحد الأقصى {max_pdf_size} حرف):\n"
        "(يمكنك إضافة عنوان بتنسيق: العنوان::النص)",
        parse_mode='Markdown')

    bot.register_next_step_handler(message, process_pdf_content)

@error_handler
def process_pdf_content(message):
    """معالجة محتوى PDF"""
    user_id = message.chat.id
    pdf_cost = POINTS_CONFIG['pdf_cost']
    max_pdf_size = int(get_setting('max_pdf_size', '10000'))

    content = message.text

    if len(content) > max_pdf_size:
        bot.send_message(user_id, get_text('too_long', user_id, length=max_pdf_size))
        return

    update_user_points(user_id, -pdf_cost, 'إنشاء PDF')

    title = None
    if "::" in content:
        parts = content.split("::", 1)
        title = parts[0].strip()
        content = parts[1].strip()

    try:
        pdf = FPDF()
        pdf.add_page()

        try:
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            pdf.set_font('DejaVu', '', 12)
        except:
            pdf.set_font('Arial', '', 12)

        if title:
            pdf.set_font_size(16)
            pdf.cell(0, 10, title, ln=True, align='C')
            pdf.ln(10)

        pdf.set_font_size(10)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.cell(0, 8, f"تاريخ الإنشاء: {date_str}", ln=True)
        pdf.ln(5)

        pdf.set_font_size(12)
        pdf.multi_cell(0, 10, content)

        pdf.ln(10)
        pdf.set_font_size(10)
        pdf.cell(0, 8, "تم الإنشاء بواسطة MalikBot2025 Pro", ln=True, align='C')

        filename = f"document_{user_id}_{int(time.time())}.pdf"
        pdf.output(filename)

        with open(filename, 'rb') as f:
            bot.send_document(user_id, f, caption=get_text('pdf_created', user_id))

        try:
            with get_db_cursor() as cursor:
                file_size = os.path.getsize(filename)
                cursor.execute("INSERT INTO pdf_files(user_id, filename, file_size) VALUES(?, ?, ?)", (user_id, filename, file_size))
        except:
            pass

        os.remove(filename)

    except Exception as e:
        logger.error(f"خطأ في إنشاء PDF: {e}")
        bot.send_message(user_id, "❌ حدث خطأ أثناء إنشاء PDF")
        update_user_points(user_id, pdf_cost, 'استرداد نقاط PDF')

# ===== الذكاء الاصطناعي (مع إصلاحات متكاملة) =====
@bot.message_handler(func=lambda m: m.text in [get_text('ai_assistant', m.chat.id), "🤖 الذكاء الاصطناعي"])
@error_handler
def ai_assistant_command(message):
    """معالجة طلب الذكاء الاصطناعي"""
    user_id = message.chat.id

    # التحقق من وجود مفتاح OpenAI
    if not OPENAI_KEY or OPENAI_KEY.strip() == "":
        bot.send_message(user_id, get_text('ai_no_key', user_id))
        return

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT daily_ai FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            daily_ai = result['daily_ai'] if result else 0
    except:
        daily_ai = 0

    daily_limit = int(get_setting('daily_ai_limit', '3'))
    ai_cost = POINTS_CONFIG['ai_cost']

    if daily_ai >= daily_limit:
        if get_user_points(user_id) < ai_cost:
            bot.send_message(user_id, get_text('insufficient_points', user_id, points=ai_cost))
            return

    max_ai_length = int(get_setting('max_ai_length', '1000'))

    bot.send_message(
        user_id,
        f"💬 **المساعد الذكي**\n\n"
        f"أرسل سؤالك أو طلبك (الحد الأقصى {max_ai_length} حرف):\n"
        f"📊 الطلبات اليومية: {daily_ai}/{daily_limit}\n"
        f"💰 التكلفة: {ai_cost} {get_setting('currency_name', 'نقطة')} (بعد {daily_limit} طلبات مجانية)",
        parse_mode='Markdown')

    bot.register_next_step_handler(message, process_ai_request)

@error_handler
def process_ai_request(message):
    """معالجة طلب الذكاء الاصطناعي"""
    user_id = message.chat.id
    max_ai_length = int(get_setting('max_ai_length', '1000'))
    prompt = message.text

    if len(prompt) > max_ai_length:
        bot.send_message(user_id, get_text('too_long', user_id, length=max_ai_length))
        return

    # التحقق من وجود مفتاح OpenAI
    if not OPENAI_KEY or OPENAI_KEY.strip() == "":
        bot.send_message(user_id, get_text('ai_no_key', user_id))
        return

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT daily_ai FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            daily_ai = result['daily_ai'] if result else 0
    except:
        daily_ai = 0

    daily_limit = int(get_setting('daily_ai_limit', '3'))
    ai_cost = POINTS_CONFIG['ai_cost']

    try:
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE users SET daily_ai = daily_ai + 1 WHERE user_id = ?", (user_id,))
    except:
        pass

    cost_charged = 0
    if daily_ai >= daily_limit:
        update_user_points(user_id, -ai_cost, 'استخدام الذكاء الاصطناعي')
        cost_charged = ai_cost

    processing_msg = bot.send_message(user_id, get_text('ai_thinking', user_id))

    try:
        # محاولة استخدام الإصدار الجديد من OpenAI
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Respond in Arabic if the question is in Arabic."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )

            answer = response.choices[0].message.content
            tokens_used = response.usage.total_tokens

        except ImportError:
            # استخدام الإصدار القديم
            import openai
            openai.api_key = OPENAI_KEY
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Respond in Arabic if the question is in Arabic."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )

            answer = response.choices[0].message.content
            tokens_used = response.usage.total_tokens

        except Exception as e:
            raise e

        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ai_requests(user_id, prompt, response, tokens, cost) VALUES(?, ?, ?, ?, ?)",
                    (user_id, prompt[:500], answer[:1000], tokens_used, cost_charged))
        except:
            pass

        bot.delete_message(user_id, processing_msg.message_id)
        bot.send_message(user_id, f"**🤖 الإجابة:**\n\n{answer}", parse_mode='Markdown')

    except Exception as e:
        error_msg = str(e)
        bot.delete_message(user_id, processing_msg.message_id)
        
        if "insufficient_quota" in error_msg or "exceeded" in error_msg:
            bot.send_message(user_id, get_text('ai_quota_exceeded', user_id))
        elif "authentication" in error_msg.lower() or "invalid" in error_msg.lower():
            bot.send_message(user_id, "❌ مفتاح OpenAI غير صالح أو منتهي الصلاحية.")
        elif "rate limit" in error_msg.lower():
            bot.send_message(user_id, get_text('ai_rate_limit', user_id))
        elif "timeout" in error_msg.lower():
            bot.send_message(user_id, "⏱️ انتهت مهلة الطلب. حاول مرة أخرى.")
        else:
            bot.send_message(user_id, get_text('ai_error', user_id))
        
        logger.error(f"خطأ في الذكاء الاصطناعي: {error_msg}")
        
        # استرداد النقاط إذا تم خصمها
        if cost_charged > 0:
            update_user_points(user_id, cost_charged, 'استرداد نقاط AI')

# ===== حسابي =====
@bot.message_handler(func=lambda m: m.text in [get_text('my_account', m.chat.id), "👤 حسابي"])
@error_handler
def my_account_command(message):
    """عرض معلومات حساب المستخدم"""
    user_id = message.chat.id

    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT u.*, COUNT(r.referred_id) as referral_count
                FROM users u
                LEFT JOIN referrals r ON u.user_id = r.referrer_id
                WHERE u.user_id = ?
                GROUP BY u.user_id
            """, (user_id,))

            user_data = cursor.fetchone()

            if not user_data:
                bot.send_message(user_id, get_text('user_not_found', user_id))
                return

            msg = f"👤 **معلومات الحساب**\n\n"
            msg += f"🆔 المعرف: `{user_data['user_id']}`\n"
            msg += f"👤 الاسم: {user_data['first_name']}\n"

            if user_data['username']:
                msg += f"📱 المعرف: @{user_data['username']}\n"

            msg += f"💳 النقاط: {user_data['points']:.2f}\n"
            msg += f"💰 إجمالي الأرباح: {user_data['total_earned']:.2f}\n"
            msg += f"👥 عدد المحالين: {user_data['referral_count']}\n"
            msg += f"📅 تاريخ التسجيل: {user_data['created_at'][:10]}\n"
            msg += f"🕒 آخر نشاط: {user_data['last_active'][:16]}\n\n"

            msg += f"📊 **إحصائيات اليوم:**\n"
            msg += f"• 📺 إعلانات: {user_data['daily_ads']}/{get_setting('daily_ad_limit', '10')}\n"
            msg += f"• 🤖 ذكاء اصطناعي: {user_data['daily_ai']}/{get_setting('daily_ai_limit', '3')}\n"

            if user_data['ref_code']:
                referral_link = f"https://t.me/{bot.get_me().username}?start={user_data['ref_code']}"
                msg += f"\n🔗 **رابط الإحالة:**\n`{referral_link}`"

            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton("🔄 تحديث", callback_data="refresh_account"),
                types.InlineKeyboardButton("📊 الإحصائيات", callback_data="detailed_stats"),
                types.InlineKeyboardButton("📋 سجل المعاملات", callback_data="transaction_history"),
                types.InlineKeyboardButton("🔗 رابط الإحالة", callback_data="show_referral_link"))

            bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في عرض الحساب: {e}")
        bot.send_message(user_id, "❌ حدث خطأ في عرض معلومات الحساب.")

# ===== نظام الإحالة =====
@bot.message_handler(func=lambda m: m.text in [get_text('referral', m.chat.id), "👥 نظام الإحالة"])
@error_handler
def referral_system_command(message):
    """عرض نظام الإحالة"""
    user_id = message.chat.id

    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT u.ref_code, 
                       COUNT(r.referred_id) as referral_count,
                       SUM(CASE WHEN r.bonus_paid = 1 THEN 1 ELSE 0 END) as paid_referrals
                FROM users u
                LEFT JOIN referrals r ON u.user_id = r.referrer_id
                WHERE u.user_id = ?
                GROUP BY u.user_id
            """, (user_id,))

            data = cursor.fetchone()

            if not data:
                bot.send_message(user_id, get_text('user_not_found', user_id))
                return

            referral_code = data['ref_code']
            referral_link = f"https://t.me/{bot.get_me().username}?start={referral_code}"
            referral_count = data['referral_count'] or 0
            paid_referrals = data['paid_referrals'] or 0

            cursor.execute("""
                SELECT u.first_name, u.username, r.created_at
                FROM referrals r
                JOIN users u ON r.referred_id = u.user_id
                WHERE r.referrer_id = ?
                ORDER BY r.created_at DESC
                LIMIT 5
            """, (user_id,))
            recent_referrals = cursor.fetchall()

            msg = f"👥 **نظام الإحالة**\n\n"
            msg += f"🔗 **رابط الإحالة الخاص بك:**\n`{referral_link}`\n\n"
            msg += f"💰 **المكافآت:**\n"
            msg += f"• مكافأة لكل إحالة: {POINTS_CONFIG['referral_bonus']} {get_setting('currency_name', 'نقطة')}\n"
            msg += f"• المحال يحصل على: {POINTS_CONFIG['join_bonus']} {get_setting('currency_name', 'نقطة')}\n\n"
            msg += f"📊 **إحصائياتك:**\n"
            msg += f"• إجمالي المحالين: {referral_count}\n"
            msg += f"• المحالين المدفوعين: {paid_referrals}\n"
            msg += f"• الأرباح من الإحالة: {paid_referrals * POINTS_CONFIG['referral_bonus']:.2f} {get_setting('currency_name', 'نقطة')}\n\n"

            if recent_referrals:
                msg += f"📋 **آخر 5 محالين:**\n"
                for i, ref in enumerate(recent_referrals, 1):
                    username = f"@{ref['username']}" if ref['username'] else "بدون معرف"
                    date = ref['created_at'][:10]
                    msg += f"{i}. **{ref['first_name']}** ({username}) - {date}\n"
                msg += "\n"

            msg += f"💡 **نصائح:**\n"
            msg += f"• شارك الرابط في مجموعاتك\n"
            msg += f"• أضفه في توقيعك\n"
            msg += f"• أرسله للأصدقاء مباشرة"

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton("📋 نسخ الرابط", callback_data="copy_referral_link"),
                types.InlineKeyboardButton("👥 عرض جميع المحالين", callback_data="show_referrals_list"),
                types.InlineKeyboardButton("📊 إحصائيات مفصلة", callback_data="referral_stats"))

            bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في عرض نظام الإحالة: {e}")
        bot.send_message(user_id, "❌ حدث خطأ في عرض نظام الإحالة.")

# ===== سحب النقاط =====
@bot.message_handler(func=lambda m: m.text in [get_text('withdraw', m.chat.id), "💳 سحب النقاط"])
@error_handler
def withdraw_points_command(message):
    """معالجة طلب سحب النقاط"""
    user_id = message.chat.id

    user_points = get_user_points(user_id)
    min_withdraw = POINTS_CONFIG['min_withdraw']
    withdraw_fee = POINTS_CONFIG['withdraw_fee']
    currency = get_setting('currency_name', 'نقطة')

    if user_points < min_withdraw:
        bot.send_message(
            user_id,
            f"❌ **رصيدك غير كافي للسحب**\n\n"
            f"💰 نقاطك الحالية: {user_points:.2f} {currency}\n"
            f"📊 الحد الأدنى للسحب: {min_withdraw} {currency}\n"
            f"💸 رسوم السحب: {withdraw_fee} {currency}\n\n"
            f"💡 يمكنك ربح المزيد من النقاط من خلال:\n"
            f"• مشاهدة الإعلانات\n• إحالة الأصدقاء\n• استخدام الميزات",
            parse_mode='Markdown')
        return

    withdraw_methods = get_setting('withdraw_methods', 'paypal,wallet,bank').split(',')

    keyboard = types.InlineKeyboardMarkup(row_width=2)

    button_map = {
        'paypal': ("💳 بايبال", "withdraw_paypal"),
        'wallet': ("📱 محفظة رقمية", "withdraw_wallet"),
        'bank': ("🏦 تحويل بنكي", "withdraw_bank")
    }

    for method in withdraw_methods:
        if method in button_map:
            text, callback = button_map[method]
            keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))

    keyboard.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_withdrawal"))

    bot.send_message(
        user_id,
        f"💳 **طلب سحب النقاط**\n\n"
        f"💰 النقاط المتاحة: {user_points:.2f} {currency}\n"
        f"📊 الحد الأدنى: {min_withdraw} {currency}\n"
        f"💸 رسوم السحب: {withdraw_fee} {currency}\n"
        f"💵 المبلغ الصافي: {user_points - withdraw_fee:.2f} {currency}\n\n"
        f"يرجى اختيار طريقة السحب:",
        reply_markup=keyboard,
        parse_mode='Markdown')

# ===== المساعدة =====
@bot.message_handler(func=lambda m: m.text in [get_text('help', m.chat.id), "❓ المساعدة"])
@bot.message_handler(commands=['help'])
@error_handler
def help_command(message):
    """عرض رسالة المساعدة"""
    user_id = message.chat.id

    help_text = f"""
❓ **مركز المساعدة - MalikBot2025 Pro**

📋 **الأوامر المتاحة:**
• /start - بدء البوت والتسجيل
• /help - عرض رسالة المساعدة
• /stats - عرض إحصائياتك
• /referral - عرض رابط الإحالة

🎯 **الميزات الرئيسية:**

1. 💰 **ربح النقاط:**
   • مشاهدة الإعلانات ({POINTS_CONFIG['ad_bonus']} {get_setting('currency_name', 'نقطة')} لكل إعلان)
   • إحالة الأصدقاء ({POINTS_CONFIG['referral_bonus']} {get_setting('currency_name', 'نقطة')} لكل صديق)
   • مكافأة الانضمام ({POINTS_CONFIG['join_bonus']} {get_setting('currency_name', 'نقطة')})
   • الحد اليومي للإعلانات: {get_setting('daily_ad_limit', '10')}

2. 📄 **إنشاء PDF:**
   • تحويل النصوص إلى مستندات PDF
   • تكلفة الخدمة: {POINTS_CONFIG['pdf_cost']} {get_setting('currency_name', 'نقطة')}
   • الحد الأقصى للنص: {get_setting('max_pdf_size', '10000')} حرف

3. 🤖 **الذكاء الاصطناعي:**
   • محادثة مع مساعد ذكي
   • تكلفة الخدمة: {POINTS_CONFIG['ai_cost']} {get_setting('currency_name', 'نقطة')}
   • الحد اليومي: {get_setting('daily_ai_limit', '3')} طلبات مجانية
   • الحد الأقصى للسؤال: {get_setting('max_ai_length', '1000')} حرف

4. 👥 **نظام الإحالة:**
   • احصل على نقاط عن طريق إحالة الأصدقاء
   • رابط إحالة فريد لكل مستخدم

5. 💳 **سحب النقاط:**
   • الحد الأدنى للسحب: {POINTS_CONFIG['min_withdraw']} {get_setting('currency_name', 'نقطة')}
   • رسوم السحب: {POINTS_CONFIG['withdraw_fee']} {get_setting('currency_name', 'نقطة')}
   • طرق السحب المتاحة: {get_setting('withdraw_methods', 'paypal,wallet,bank')}

🔒 **الأمان والخصوصية:**
• جميع المعاملات مسجلة
• نظام تحقق من الاشتراك
• تسجيل كامل للعمليات
• نظام نسخ احتياطي تلقائي

📞 **الدعم والمساعدة:**
{CHANNEL if CHANNEL else "لا توجد قناة محددة"}

🕒 **معلومات النظام:**
• النسخة: 2.0 (مُحسنة)
• آخر تحديث: {datetime.datetime.now().strftime('%Y-%m-%d')}
• حالة الخادم: ✅ نشط
    """

    bot.send_message(user_id, help_text, parse_mode='Markdown')

# ===== لوحة تحكم المشرف =====
@bot.message_handler(func=lambda m: m.text in [get_text('control_panel', m.chat.id), "📊 لوحة التحكم"])
@error_handler
def admin_panel_command(message):
    """فتح لوحة تحكم المشرف"""
    user_id = message.chat.id

    if user_id != ADMIN_ID:
        bot.send_message(user_id, get_text('admin_only', user_id))
        return

    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN DATE(created_at) = DATE('now') THEN 1 END) as today_users,
                    SUM(points) as total_points,
                    COUNT(DISTINCT ref_by) as referrers
                FROM users
            """)
            stats = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*) as active_today 
                FROM users 
                WHERE DATE(last_active) = DATE('now')
            """)
            active_stats = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*) as pending_withdrawals
                FROM withdrawals
                WHERE status = 'pending'
            """)
            withdraw_stats = cursor.fetchone()

        total_users = stats['total_users'] if stats else 0
        today_users = stats['today_users'] if stats else 0
        total_points = stats['total_points'] if stats else 0
        referrers = stats['referrers'] if stats else 0
        active_today = active_stats['active_today'] if active_stats else 0
        pending_withdrawals = withdraw_stats['pending_withdrawals'] if withdraw_stats else 0

        msg = f"👑 **لوحة تحكم المشرف - MalikBot2025 Pro**\n\n"
        msg += f"📊 **إحصائيات سريعة:**\n"
        msg += f"• 👥 إجمالي المستخدمين: {total_users}\n"
        msg += f"• 📈 مستخدمين اليوم: {today_users}\n"
        msg += f"• 🎯 نشطين اليوم: {active_today}\n"
        msg += f"• 💰 إجمالي النقاط: {total_points:.2f}\n"
        msg += f"• 👥 عدد المشيرين: {referrers}\n"
        msg += f"• 📤 طلبات سحب معلقة: {pending_withdrawals}\n"
        msg += f"• 🛠️ وضع الصيانة: {'✅ مفعل' if get_setting('maintenance_mode', 'off').lower() == 'on' else '❌ معطل'}\n"
        msg += f"• 🤖 الذكاء الاصطناعي: {'✅ مفعل' if OPENAI_KEY else '❌ معطل'}\n\n"

        msg += f"💻 **معلومات النظام:**\n"
        msg += f"• 🐍 Python: {sys.version.split()[0]}\n"
        msg += f"• 📊 حجم قاعدة البيانات: {os.path.getsize(DB_FILE) / 1024 / 1024:.2f} MB\n"
        msg += f"• 🕒 وقت التشغيل: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("📊 إحصائيات مفصلة", callback_data="admin_stats"),
            types.InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users"),
            types.InlineKeyboardButton("💰 إدارة النقاط", callback_data="admin_points"),
            types.InlineKeyboardButton("📢 إرسال عام", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("⚙️ إعدادات النظام", callback_data="admin_settings"),
            types.InlineKeyboardButton("💾 نسخة احتياطية", callback_data="admin_backup"),
            types.InlineKeyboardButton("📋 سجلات النظام", callback_data="admin_logs"),
            types.InlineKeyboardButton("🔄 تحديث النظام", callback_data="admin_update"))

        bot.send_message(user_id, msg, reply_markup=keyboard, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في لوحة التحكم: {e}")
        bot.send_message(user_id, f"❌ خطأ في لوحة التحكم: {e}")

# ===== وظائف خلفية =====
def backup_worker():
    """عامل النسخ الاحتياطي التلقائي"""
    while True:
        try:
            time.sleep(24 * 3600)
            if get_setting('auto_backup', 'true').lower() == 'true':
                create_backup()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"خطأ في النسخ الاحتياطي التلقائي: {e}")
            time.sleep(3600)

def reset_worker():
    """عامل إعادة تعيين العدادات اليومية"""
    while True:
        try:
            time.sleep(3600)
            reset_daily_counts()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"خطأ في إعادة التعيين: {e}")
            time.sleep(3600)

def create_backup():
    """إنشاء نسخة احتياطية"""
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")

        backup_conn = sqlite3.connect(backup_file)
        with get_db_connection() as source_conn:
            source_conn.backup(backup_conn)
        backup_conn.close()

        compressed_file = f"{backup_file}.gz"
        with open(backup_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        os.remove(backup_file)
        cleanup_old_backups()

        logger.info(f"✅ تم إنشاء نسخة احتياطية: {compressed_file}")

        if get_setting('admin_notifications', 'true').lower() == 'true':
            try:
                file_size = os.path.getsize(compressed_file) / 1024 / 1024
                bot.send_message(
                    ADMIN_ID,
                    f"💾 **نسخة احتياطية تلقائية**\n\n"
                    f"📁 الملف: `{compressed_file}`\n"
                    f"📊 الحجم: {file_size:.2f} MB\n"
                    f"📅 التاريخ: {timestamp}",
                    parse_mode='Markdown')
            except:
                pass

        return compressed_file

    except Exception as e:
        logger.error(f"❌ خطأ في النسخ الاحتياطي: {e}")
        return None

def cleanup_old_backups():
    """تنظيف النسخ الاحتياطية القديمة"""
    try:
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=BACKUP_RETENTION_DAYS)

        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.db.gz'):
                file_path = os.path.join(BACKUP_DIR, filename)
                file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_time < cutoff_date:
                    os.remove(file_path)
                    logger.info(f"🗑️ تم حذف نسخة احتياطية قديمة: {filename}")

    except Exception as e:
        logger.error(f"خطأ في تنظيف النسخ الاحتياطية: {e}")

# ===== تنظيف الموارد =====
def cleanup(signum=None, frame=None):
    """تنظيف الموارد عند إنهاء البرنامج"""
    logger.info("🛑 جارٍ إنهاء البوت وتنظيف الموارد...")

    try:
        create_backup()
        logger.info("✅ تم التنظيف بنجاح")
    except Exception as e:
        logger.error(f"❌ خطأ أثناء التنظيف: {e}")

    os._exit(0)  # استخدام os._exit بدلاً من sys.exit لتجنب تكرار التنظيف

# تسجيل معالجات الإشارات
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)
atexit.register(cleanup)

# ===== التحقق من الإعدادات =====
def check_configuration():
    """التحقق من تكوين البوت"""
    errors = []

    if not BOT_TOKEN:
        errors.append("❌ لم يتم تعيين توكن البوت (BOT_TOKEN)")

    if ADMIN_ID == 0:
        errors.append("❌ لم يتم تعيين معرف المشرف (ADMIN_ID)")

    return errors

# ===== بدء التشغيل =====
def run_bot():
    """الدالة الرئيسية لتشغيل البوت"""

    print("=" * 60)
    print("🤖 **MalikBot2025 Pro - النسخة المحسنة المطورة**")
    print("=" * 60)

    config_errors = check_configuration()

    if config_errors:
        print("⚠️ **تحذيرات التكوين:**")
        for error in config_errors:
            print(error)

        if "❌" in config_errors[0]:
            print("\n❌ لا يمكن تشغيل البوت بدون التوكن ومعرف المشرف!")
            return

    # تحسين تهيئة قاعدة البيانات
    print("🔍 جاري التحقق من قاعدة البيانات...")
    
    # التحقق من وجود ملف قاعدة البيانات
    if not os.path.exists(DB_FILE):
        print("🆕 إنشاء قاعدة بيانات جديدة...")
        with open(DB_FILE, 'w') as f:
            pass  # إنشاء ملف فارغ
        
    # تهيئة قاعدة البيانات
    if not init_database():
        print("⚠️ تم إنشاء قاعدة بيانات أساسية...")
    
    try:
        bot_info = bot.get_me()
        print(f"✅ البوت: @{bot_info.username}")
        print(f"🆔 معرف البوت: {bot_info.id}")
        print(f"👤 اسم البوت: {bot_info.first_name}")
    except Exception as e:
        print(f"❌ لا يمكن الاتصال بخوادم Telegram: {e}")
        print("تأكد من صحة التوكن!")
        return

    print(f"👑 المشرف: {ADMIN_ID}")
    print(f"📢 القناة: {CHANNEL if CHANNEL else 'غير محددة'}")
    print(f"💾 قاعدة البيانات: {DB_FILE}")
    print(f"🤖 الذكاء الاصطناعي: {'✅ مفعل' if OPENAI_KEY and OPENAI_KEY.strip() != '' else '❌ معطل'}")
    print(f"🛠️ وضع الصيانة: {'✅ مفعل' if get_setting('maintenance_mode', 'off').lower() == 'on' else '❌ معطل'}")
    print("✅ التحقق من القناة: معطل مؤقتًا (لتفعيله لاحقًا)")
    print("=" * 60)

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"👥 عدد المستخدمين المسجلين: {user_count}")

            cursor.execute("SELECT SUM(points) FROM users")
            total_points = cursor.fetchone()[0] or 0
            print(f"💰 إجمالي النقاط: {total_points:.2f}")
    except Exception as e:
        print(f"⚠️ لا يمكن قراءة قاعدة البيانات: {e}")

    try:
        threading.Thread(target=backup_worker, daemon=True).start()
        threading.Thread(target=reset_worker, daemon=True).start()
        print("✅ تم تشغيل الوظائف الخلفية")
    except Exception as e:
        print(f"⚠️ خطأ في تشغيل الوظائف الخلفية: {e}")

    print("🚀 بدء تشغيل البوت...")
    print("=" * 60)

    try:
        bot.polling(none_stop=True, interval=1, timeout=60)
    except KeyboardInterrupt:
        print("\n⏹️ إيقاف البوت...")
        cleanup()
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        cleanup()

# ===== نقطة الدخول الرئيسية =====
if __name__ == "__main__":
    run_bot()
