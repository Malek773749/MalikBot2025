#!/usr/bin/env python3
"""
Malik Services Bot - بوت خدمات رقمية متكامل بنظام النقاط
إصدار شامل - ملف واحد فقط
"""

# ==================== المكتبات المطلوبة ====================
import os
import sys
import logging
import sqlite3
import json
import random
import string
import asyncio
import hashlib
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import traceback
import re
from decimal import Decimal, ROUND_HALF_UP

# مكتبات التليجرام
try:
    from telegram import (
        Update, InlineKeyboardButton, InlineKeyboardMarkup,
        InputFile, InputMediaPhoto, InputMediaVideo
    )
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        CallbackQueryHandler, filters, ContextTypes,
        ConversationHandler
    )
    from telegram.error import TelegramError, BadRequest
except ImportError:
    print("❌ يرجى تثبيت مكتبة python-telegram-bot:")
    print("pip install python-telegram-bot[job-queue]==20.7")
    sys.exit(1)

# مكتبات PDF
try:
    from fpdf import FPDF
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    import PyPDF2
except ImportError:
    print("⚠️  بعض مكتبات PDF غير مثبتة، سيتم استخدام بدائل")

# مكتبات مساعدة
try:
    import pytz
    from forex_python.converter import CurrencyRates
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("⚠️  بعض المكتبات المساعدة غير مثبتة")

# ==================== الإعدادات والتكوين ====================
class Config:
    """إعدادات البوت"""
    # التوكن والإدارة
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7096820738:AAGe56KhU5HkIKGfP_T3sWLL1N7y8W4j0dY")
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "524892378").split(",")] if os.getenv("ADMIN_IDS") else [524892378]
    
    # إعدادات النقاط
    POINTS = {
        "welcome": 5,  # نقاط الترحيب
        "ad_view": 3,  # مشاهدة إعلان
        "referral": 10,  # إحالة صديق
        "daily_min": 5,  # أقل مكافأة يومية
        "daily_max": 20,  # أعلى مكافأة يومية
        "game_min": 2,   # أقل مكافأة لعبة
        "game_max": 15,  # أعلى مكافأة لعبة
        "pdf_conversion": 0.5,  # تكلفة تحويل PDF
        "pdf_merge": 1.0,  # تكلفة دمج PDF
        "pdf_compress": 0.3,  # تكلفة ضغط PDF
        "min_withdraw": 100,  # أقل سحب للنقاط
        "max_points_per_day": 100  # أقصى نقاط يومياً
    }
    
    # إعدادات الوقت
    TIME_LIMITS = {
        "ad_cooldown": 300,  # 5 دقائق بين الإعلانات (بالثواني)
        "daily_cooldown": 86400,  # 24 ساعة للمكافأة اليومية
        "game_cooldown": 60,  # دقيقة بين الألعاب
        "referral_cooldown": 3600  # ساعة بين الإحالات
    }
    
    # إعدادات PDF
    PDF_SETTINGS = {
        "max_file_size": 20 * 1024 * 1024,  # 20MB
        "max_text_length": 10000,  # 10K حرف
        "allowed_extensions": ['.pdf', '.txt', '.doc', '.docx'],
        "max_pages": 200,
        "default_font_size": 12,
        "default_margin": 20
    }
    
    # إعدادات الألعاب
    GAMES = {
        "xo_grid_size": 3,
        "number_range": (1, 100),
        "quiz_questions": [
            {"question": "ما هي عاصمة السعودية؟", "answer": "الرياض"},
            {"question": "2 + 2 = ؟", "answer": "4"},
            {"question": "ما لون التفاحة؟", "answer": "أحمر"},
        ]
    }
    
    # العملات
    CURRENCIES = ["USD", "SAR", "EUR", "GBP", "AED", "QAR", "KWD", "OMR", "BHD"]
    
    # الوحدات
    UNITS = {
        "data": ["KB", "MB", "GB", "TB"],
        "length": ["mm", "cm", "m", "km"],
        "weight": ["g", "kg", "ton"],
        "temperature": ["C", "F", "K"]
    }
    
    # الأمان
    SECURITY = {
        "max_requests_per_minute": 60,
        "ban_threshold": 100,
        "max_file_uploads": 10,
        "allowed_commands_per_hour": 100
    }
    
    # المسارات
    PATHS = {
        "database": "malik_bot.db",
        "backups": "backups/",
        "temp_files": "temp/",
        "logs": "logs/"
    }
    
    # الإعلانات
    ADS = [
        {
            "id": 1,
            "type": "text",
            "title": "📱 تطبيق جديد",
            "content": "حمل تطبيقنا الجديد واحصل على خصم 50%",
            "link": "https://example.com",
            "points": 3
        },
        {
            "id": 2,
            "type": "image",
            "title": "🎯 عرض خاص",
            "content": "اشتر الآن واحصل على هدية مجانية",
            "image_url": "https://via.placeholder.com/300",
            "link": "https://example.com/sale",
            "points": 5
        }
    ]
    
    @classmethod
    def init_directories(cls):
        """إنشاء المجلدات المطلوبة"""
        for path in cls.PATHS.values():
            if path.endswith('/'):
                os.makedirs(path, exist_ok=True)

# ==================== نظام التسجيل ====================
class Logger:
    """نظام تسجيل متقدم"""
    def __init__(self):
        Config.init_directories()
        log_file = os.path.join(Config.PATHS["logs"], "malik_bot.log")
        
        self.logger = logging.getLogger("MalikBot")
        self.logger.setLevel(logging.INFO)
        
        # تنسيق الرسائل
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # ملف السجلات
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # وحدة التحكم
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        """تسجيل معلومات"""
        self.logger.info(message)
    
    def error(self, message: str, exc_info=None):
        """تسجيل أخطاء"""
        self.logger.error(message, exc_info=exc_info)
    
    def warning(self, message: str):
        """تسجيل تحذيرات"""
        self.logger.warning(message)
    
    def debug(self, message: str):
        """تسجيل تفاصيل"""
        self.logger.debug(message)

logger = Logger()

# ==================== قاعدة البيانات المتقدمة ====================
class Database:
    """نظام قاعدة بيانات متقدم مع إدارة الاتصالات"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        """تهيئة قاعدة البيانات"""
        self.conn = sqlite3.connect(
            Config.PATHS["database"],
            check_same_thread=False,
            timeout=30
        )
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.create_indexes()
        self.seed_data()
    
    def create_tables(self):
        """إنشاء جميع الجداول"""
        tables = [
            # جدول المستخدمين
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                language_code TEXT DEFAULT 'ar',
                points DECIMAL(10,2) DEFAULT 5.0,
                total_earned DECIMAL(10,2) DEFAULT 0.0,
                referral_code VARCHAR(10) UNIQUE,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_daily TIMESTAMP,
                last_ad TIMESTAMP,
                is_premium BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                ban_reason TEXT,
                settings TEXT DEFAULT '{}'
            )
            """,
            
            # جدول المعاملات
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                type VARCHAR(20) NOT NULL,
                description TEXT,
                reference_id TEXT,
                status VARCHAR(20) DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # جدول الإعلانات
            """
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                ad_type VARCHAR(10) DEFAULT 'text',
                image_url TEXT,
                video_url TEXT,
                link TEXT,
                points INTEGER DEFAULT 1,
                views INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                created_by INTEGER,
                budget DECIMAL(10,2) DEFAULT 0.0
            )
            """,
            
            # جدول مشاهدة الإعلانات
            """
            CREATE TABLE IF NOT EXISTS ad_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ad_id INTEGER NOT NULL,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clicked BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (ad_id) REFERENCES ads(id)
            )
            """,
            
            # جدول الملفات
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type VARCHAR(10),
                file_size INTEGER,
                file_hash VARCHAR(64),
                operation_type VARCHAR(20),
                points_cost DECIMAL(5,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
            
            # جدول الألعاب
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_type VARCHAR(20) NOT NULL,
                score INTEGER,
                points_earned DECIMAL(5,2),
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
            
            # جدول الإحصائيات
            """
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                total_users INTEGER DEFAULT 0,
                new_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                total_points DECIMAL(15,2) DEFAULT 0.0,
                ads_viewed INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                files_converted INTEGER DEFAULT 0,
                revenue DECIMAL(10,2) DEFAULT 0.0
            )
            """,
            
            # جدول الإعدادات
            """
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(50) PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # جدول السحب
            """
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                method VARCHAR(20),
                status VARCHAR(20) DEFAULT 'pending',
                details TEXT,
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
            
            # جدول الأخطاء
            """
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                error_type VARCHAR(50),
                error_message TEXT,
                stack_trace TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for table_sql in tables:
            try:
                self.cursor.execute(table_sql)
            except sqlite3.Error as e:
                logger.error(f"خطأ في إنشاء الجداول: {e}")
        
        self.conn.commit()
    
    def create_indexes(self):
        """إنشاء فهارس لتحسين الأداء"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_ad_views_user_ad ON ad_views(user_id, ad_id)",
            "CREATE INDEX IF NOT EXISTS idx_games_user_id ON games(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id)"
        ]
        
        for index_sql in indexes:
            try:
                self.cursor.execute(index_sql)
            except sqlite3.Error as e:
                logger.error(f"خطأ في إنشاء الفهارس: {e}")
        
        self.conn.commit()
    
    def seed_data(self):
        """إدخال بيانات أولية"""
        # إعدادات النظام
        settings = [
            ("app_name", "Malik Services Bot", "اسم التطبيق"),
            ("app_version", "2.0.0", "إصدار البوت"),
            ("maintenance_mode", "0", "وضع الصيانة"),
            ("new_user_points", str(Config.POINTS["welcome"]), "نقاط المستخدم الجديد"),
            ("min_withdraw", str(Config.POINTS["min_withdraw"]), "الحد الأدنى للسحب"),
            ("currency", "USD", "العملة الافتراضية"),
            ("timezone", "Asia/Riyadh", "المنطقة الزمنية")
        ]
        
        for key, value, description in settings:
            self.cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)",
                (key, value, description)
            )
        
        # إضافة إعلانات افتراضية
        for ad in Config.ADS:
            self.cursor.execute(
                """INSERT OR IGNORE INTO ads 
                (title, content, ad_type, image_url, link, points) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (ad["title"], ad["content"], ad["type"], 
                 ad.get("image_url"), ad.get("link"), ad.get("points", 1))
            )
        
        self.conn.commit()
    
    # ===== عمليات المستخدمين =====
    def get_user(self, user_id: int) -> Optional[Dict]:
        """الحصول على بيانات مستخدم"""
        try:
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"خطأ في جلب بيانات المستخدم {user_id}: {e}")
            return None
    
    def create_user(self, user_id: int, username: str, first_name: str, 
                   last_name: str = "", referred_by: int = None) -> Dict:
        """إنشاء مستخدم جديد"""
        try:
            referral_code = self.generate_referral_code()
            
            self.cursor.execute(
                """INSERT INTO users 
                (user_id, username, first_name, last_name, referral_code, referred_by, points) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, first_name, last_name, referral_code, referred_by, 
                 Config.POINTS["welcome"])
            )
            
            # تسجيل معاملة نقطة الترحيب
            self.add_transaction(
                user_id, 
                Config.POINTS["welcome"], 
                "welcome", 
                "نقاط ترحيبية"
            )
            
            # تحديث عداد الإحالات إذا كان هناك محيل
            if referred_by:
                self.cursor.execute(
                    "UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?",
                    (referred_by,)
                )
                # منح نقاط الإحالة للمحيل
                self.add_points(referred_by, Config.POINTS["referral"], "referral")
            
            self.conn.commit()
            return self.get_user(user_id)
        except sqlite3.Error as e:
            logger.error(f"خطأ في إنشاء مستخدم {user_id}: {e}")
            return {}
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """تحديث بيانات مستخدم"""
        try:
            if not kwargs:
                return False
            
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            
            self.cursor.execute(
                f"UPDATE users SET {set_clause} WHERE user_id = ?",
                values
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"خطأ في تحديث المستخدم {user_id}: {e}")
            return False
    
    def add_points(self, user_id: int, amount: float, 
                   trans_type: str, description: str = "", 
                   reference_id: str = None) -> bool:
        """إضافة نقاط للمستخدم وتسجيل المعاملة"""
        try:
            # تحديث نقاط المستخدم
            self.cursor.execute(
                """UPDATE users 
                SET points = points + ?, total_earned = total_earned + ? 
                WHERE user_id = ?""",
                (amount, max(amount, 0), user_id)
            )
            
            # تسجيل المعاملة
            self.add_transaction(user_id, amount, trans_type, description, reference_id)
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"خطأ في إضافة نقاط للمستخدم {user_id}: {e}")
            return False
    
    def deduct_points(self, user_id: int, amount: float, 
                     trans_type: str, description: str = "") -> bool:
        """خصم نقاط من المستخدم"""
        try:
            # التحقق من رصيد المستخدم
            user = self.get_user(user_id)
            if not user or user['points'] < amount:
                return False
            
            return self.add_points(user_id, -amount, trans_type, description)
        except sqlite3.Error as e:
            logger.error(f"خطأ في خصم نقاط من المستخدم {user_id}: {e}")
            return False
    
    def get_user_stats(self, user_id: int) -> Dict:
        """الحصول على إحصائيات مستخدم"""
        stats = {
            "user": self.get_user(user_id),
            "today_points": 0,
            "week_points": 0,
            "total_transactions": 0,
            "total_ads": 0,
            "total_games": 0,
            "rank": 0
        }
        
        if not stats["user"]:
            return stats
        
        try:
            # نقاط اليوم
            self.cursor.execute(
                """SELECT COALESCE(SUM(amount), 0) 
                FROM transactions 
                WHERE user_id = ? AND DATE(created_at) = DATE('now')""",
                (user_id,)
            )
            stats["today_points"] = self.cursor.fetchone()[0]
            
            # نقاط الأسبوع
            self.cursor.execute(
                """SELECT COALESCE(SUM(amount), 0) 
                FROM transactions 
                WHERE user_id = ? AND created_at >= DATE('now', '-7 days')""",
                (user_id,)
            )
            stats["week_points"] = self.cursor.fetchone()[0]
            
            # عدد المعاملات
            self.cursor.execute(
                "SELECT COUNT(*) FROM transactions WHERE user_id = ?",
                (user_id,)
            )
            stats["total_transactions"] = self.cursor.fetchone()[0]
            
            # عدد الإعلانات
            self.cursor.execute(
                "SELECT COUNT(*) FROM ad_views WHERE user_id = ?",
                (user_id,)
            )
            stats["total_ads"] = self.cursor.fetchone()[0]
            
            # عدد الألعاب
            self.cursor.execute(
                "SELECT COUNT(*) FROM games WHERE user_id = ?",
                (user_id,)
            )
            stats["total_games"] = self.cursor.fetchone()[0]
            
            # الترتيب
            self.cursor.execute(
                """SELECT COUNT(*) + 1 
                FROM users 
                WHERE points > (SELECT points FROM users WHERE user_id = ?)""",
                (user_id,)
            )
            stats["rank"] = self.cursor.fetchone()[0]
            
        except sqlite3.Error as e:
            logger.error(f"خطأ في جلب إحصائيات المستخدم {user_id}: {e}")
        
        return stats
    
    # ===== المعاملات =====
    def add_transaction(self, user_id: int, amount: float, 
                       trans_type: str, description: str = "", 
                       reference_id: str = None) -> bool:
        """تسجيل معاملة جديدة"""
        try:
            self.cursor.execute(
                """INSERT INTO transactions 
                (user_id, amount, type, description, reference_id) 
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, trans_type, description, reference_id)
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"خطأ في تسجيل معاملة للمستخدم {user_id}: {e}")
            return False
    
    def get_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        """الحصول على معاملات المستخدم"""
        try:
            self.cursor.execute(
                """SELECT * FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?""",
                (user_id, limit)
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"خطأ في جلب معاملات المستخدم {user_id}: {e}")
            return []
    
    # ===== الإعلانات =====
    def get_available_ad(self, user_id: int) -> Optional[Dict]:
        """الحصول على إعلان متاح للمستخدم"""
        try:
            # تجنب تكرار الإعلانات
            self.cursor.execute(
                """SELECT a.* FROM ads a
                LEFT JOIN ad_views av ON a.id = av.ad_id AND av.user_id = ?
                WHERE a.is_active = 1 
                AND (av.id IS NULL OR av.viewed_at < DATETIME('now', '-5 minutes'))
                ORDER BY RANDOM()
                LIMIT 1""",
                (user_id,)
            )
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"خطأ في جلب إعلان للمستخدم {user_id}: {e}")
            return None
    
    def record_ad_view(self, user_id: int, ad_id: int, clicked: bool = False) -> bool:
        """تسجيل مشاهدة إعلان"""
        try:
            self.cursor.execute(
                """INSERT INTO ad_views (user_id, ad_id, clicked) 
                VALUES (?, ?, ?)""",
                (user_id, ad_id, clicked)
            )
            
            # تحديث إحصائيات الإعلان
            self.cursor.execute(
                "UPDATE ads SET views = views + 1 WHERE id = ?",
                (ad_id,)
            )
            
            if clicked:
                self.cursor.execute(
                    "UPDATE ads SET clicks = clicks + 1 WHERE id = ?",
                    (ad_id,)
                )
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"خطأ في تسجيل مشاهدة إعلان: {e}")
            return False
    
    # ===== الإحصائيات =====
    def update_daily_stats(self):
        """تحديث الإحصائيات اليومية"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # عدد المستخدمين الجدد
            self.cursor.execute(
                """SELECT COUNT(*) FROM users 
                WHERE DATE(join_date) = ?""",
                (today,)
            )
            new_users = self.cursor.fetchone()[0]
            
            # المستخدمين النشطين اليوم
            self.cursor.execute(
                """SELECT COUNT(DISTINCT user_id) 
                FROM transactions 
                WHERE DATE(created_at) = ?""",
                (today,)
            )
            active_users = self.cursor.fetchone()[0]
            
            # إجمالي المستخدمين
            self.cursor.execute("SELECT COUNT(*) FROM users")
            total_users = self.cursor.fetchone()[0]
            
            # إجمالي النقاط
            self.cursor.execute("SELECT SUM(points) FROM users")
            total_points = self.cursor.fetchone()[0] or 0
            
            # الإعلانات المشاهدة اليوم
            self.cursor.execute(
                """SELECT COUNT(*) FROM ad_views 
                WHERE DATE(viewed_at) = ?""",
                (today,)
            )
            ads_viewed = self.cursor.fetchone()[0]
            
            # الألعاب اليوم
            self.cursor.execute(
                """SELECT COUNT(*) FROM games 
                WHERE DATE(created_at) = ?""",
                (today,)
            )
            games_played = self.cursor.fetchone()[0]
            
            # الملفات المحولة اليوم
            self.cursor.execute(
                """SELECT COUNT(*) FROM files 
                WHERE DATE(created_at) = ?""",
                (today,)
            )
            files_converted = self.cursor.fetchone()[0]
            
            # إدراج أو تحديث الإحصائيات
            self.cursor.execute(
                """INSERT OR REPLACE INTO statistics 
                (date, total_users, new_users, active_users, total_points, 
                 ads_viewed, games_played, files_converted) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (today, total_users, new_users, active_users, total_points,
                 ads_viewed, games_played, files_converted)
            )
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"خطأ في تحديث الإحصائيات: {e}")
            return False
    
    # ===== أدوات مساعدة =====
    def generate_referral_code(self) -> str:
        """توليد كود إحالة فريد"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            self.cursor.execute(
                "SELECT COUNT(*) FROM users WHERE referral_code = ?",
                (code,)
            )
            if self.cursor.fetchone()[0] == 0:
                return code
    
    def get_top_users(self, limit: int = 10) -> List[Dict]:
        """الحصول على أفضل المستخدمين"""
        try:
            self.cursor.execute(
                """SELECT user_id, username, first_name, points, referral_count 
                FROM users 
                WHERE is_banned = 0 
                ORDER BY points DESC 
                LIMIT ?""",
                (limit,)
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"خطأ في جلب أفضل المستخدمين: {e}")
            return []
    
    def get_system_stats(self) -> Dict:
        """إحصائيات النظام"""
        stats = {}
        try:
            # إجمالي المستخدمين
            self.cursor.execute("SELECT COUNT(*) FROM users")
            stats["total_users"] = self.cursor.fetchone()[0]
            
            # المستخدمين النشطين اليوم
            self.cursor.execute(
                """SELECT COUNT(DISTINCT user_id) FROM transactions 
                WHERE DATE(created_at) = DATE('now')"""
            )
            stats["active_today"] = self.cursor.fetchone()[0]
            
            # إجمالي النقاط
            self.cursor.execute("SELECT SUM(points) FROM users")
            stats["total_points"] = self.cursor.fetchone()[0] or 0
            
            # إجمالي المعاملات
            self.cursor.execute("SELECT COUNT(*) FROM transactions")
            stats["total_transactions"] = self.cursor.fetchone()[0]
            
            # الإعلانات المشاهدة
            self.cursor.execute("SELECT SUM(views) FROM ads")
            stats["total_ad_views"] = self.cursor.fetchone()[0] or 0
            
            # الألعاب
            self.cursor.execute("SELECT COUNT(*) FROM games")
            stats["total_games"] = self.cursor.fetchone()[0]
            
        except sqlite3.Error as e:
            logger.error(f"خطأ في جلب إحصائيات النظام: {e}")
        
        return stats
    
    def backup_database(self) -> bool:
        """إنشاء نسخة احتياطية من قاعدة البيانات"""
        try:
            backup_file = os.path.join(
                Config.PATHS["backups"],
                f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
            
            # إنشاء نسخة من قاعدة البيانات
            backup_conn = sqlite3.connect(backup_file)
            with backup_conn:
                self.conn.backup(backup_conn)
            backup_conn.close()
            
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_file}")
            return True
        except sqlite3.Error as e:
            logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")
            return False
    
    def close(self):
        """إغلاق الاتصال بقاعدة البيانات"""
        try:
            self.conn.close()
        except sqlite3.Error as e:
            logger.error(f"خطأ في إغلاق قاعدة البيانات: {e}")

# إنشاء كائن قاعدة البيانات
db = Database()

# ==================== أدوات PDF المتقدمة ====================
class PDFManager:
    """مدير PDF متقدم"""
    
    @staticmethod
    def text_to_pdf(text: str, filename: str = "document.pdf", 
                   font_size: int = 12, margin: int = 20) -> BytesIO:
        """تحويل النص إلى PDF مع دعم العربية"""
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # دعم اللغة العربية
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            pdf.set_font('DejaVu', '', font_size)
            
            # إضافة الهيدر
            pdf.set_font('DejaVu', 'B', 16)
            pdf.cell(0, 10, 'مستند محول من بوت مالك للخدمات', 0, 1, 'C')
            pdf.ln(5)
            
            # إضافة التاريخ
            pdf.set_font('DejaVu', 'I', 10)
            pdf.cell(0, 10, f'التاريخ: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
            pdf.ln(5)
            
            # إضافة النص الرئيسي
            pdf.set_font('DejaVu', '', font_size)
            pdf.multi_cell(0, 10, text)
            
            # إضافة التذييل
            pdf.ln(10)
            pdf.set_font('DejaVu', 'I', 10)
            pdf.cell(0, 10, 'تم الإنشاء بواسطة Malik Services Bot', 0, 1, 'C')
            
            # حفظ في بايتس
            pdf_bytes = pdf.output(dest='S').encode('latin1')
            return BytesIO(pdf_bytes)
            
        except Exception as e:
            logger.error(f"خطأ في تحويل النص إلى PDF: {e}")
            # بديل بسيط
            buffer = BytesIO()
            buffer.write(f"مستند PDF\n\n{text}\n\nتم الإنشاء في {datetime.now()}".encode('utf-8'))
            buffer.seek(0)
            return buffer
    
    @staticmethod
    def merge_pdfs(pdf_files: List[BytesIO]) -> BytesIO:
        """دمج عدة ملفات PDF"""
        try:
            merger = PyPDF2.PdfMerger()
            
            for pdf_file in pdf_files:
                merger.append(pdf_file)
            
            output = BytesIO()
            merger.write(output)
            merger.close()
            output.seek(0)
            
            return output
        except Exception as e:
            logger.error(f"خطأ في دمج ملفات PDF: {e}")
            return BytesIO(b"خطأ في دمج الملفات")
    
    @staticmethod
    def compress_pdf(input_pdf: BytesIO, quality: int = 50) -> BytesIO:
        """ضغط ملف PDF"""
        try:
            # هذه مكتبة مبسطة للضغط
            reader = PyPDF2.PdfReader(input_pdf)
            writer = PyPDF2.PdfWriter()
            
            for page in reader.pages:
                writer.add_page(page)
            
            output = BytesIO()
            writer.write(output)
            output.seek(0)
            
            return output
        except Exception as e:
            logger.error(f"خطأ في ضغط PDF: {e}")
            return input_pdf
    
    @staticmethod
    def get_pdf_info(pdf_file: BytesIO) -> Dict:
        """الحصول على معلومات ملف PDF"""
        try:
            reader = PyPDF2.PdfReader(pdf_file)
            return {
                "pages": len(reader.pages),
                "size": f"{len(pdf_file.getvalue()) / 1024:.2f} KB",
                "encrypted": reader.is_encrypted,
                "metadata": reader.metadata or {}
            }
        except Exception as e:
            logger.error(f"خطأ في قراءة معلومات PDF: {e}")
            return {"pages": 0, "size": "0 KB", "encrypted": False}

# ==================== أدوات يومية متقدمة ====================
class DailyTools:
    """أدوات يومية متقدمة"""
    
    @staticmethod
    def calculate_installment(amount: float, months: int, 
                             interest_rate: float = 0) -> Dict:
        """حاسبة الأقساط المتقدمة"""
        try:
            if interest_rate > 0:
                monthly_rate = interest_rate / 12 / 100
                monthly_payment = amount * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
                total_payment = monthly_payment * months
                total_interest = total_payment - amount
            else:
                monthly_payment = amount / months
                total_payment = amount
                total_interest = 0
            
            return {
                "amount": round(amount, 2),
                "months": months,
                "interest_rate": interest_rate,
                "monthly_payment": round(monthly_payment, 2),
                "total_payment": round(total_payment, 2),
                "total_interest": round(total_interest, 2),
                "payment_schedule": [
                    {
                        "month": i + 1,
                        "payment": round(monthly_payment, 2),
                        "remaining": round(max(total_payment - (monthly_payment * (i + 1)), 0), 2)
                    }
                    for i in range(min(months, 12))  # أول 12 شهر فقط
                ]
            }
        except Exception as e:
            logger.error(f"خطأ في حاسبة الأقساط: {e}")
            return {}
    
    @staticmethod
    def calculate_profit(principal: float, rate: float, 
                        period: int, compound: bool = False) -> Dict:
        """حاسبة الأرباح المتقدمة"""
        try:
            if compound:
                # فائدة مركبة
                amount = principal * (1 + rate/100) ** period
                profit = amount - principal
            else:
                # فائدة بسيطة
                profit = principal * rate/100 * period
                amount = principal + profit
            
            return {
                "principal": round(principal, 2),
                "rate": rate,
                "period": period,
                "compound": compound,
                "profit": round(profit, 2),
                "total": round(amount, 2),
                "roi": round((profit / principal) * 100, 2) if principal > 0 else 0,
                "monthly_profit": round(profit / (period * 12), 2) if period > 0 else 0
            }
        except Exception as e:
            logger.error(f"خطأ في حاسبة الأرباح: {e}")
            return {}
    
    @staticmethod
    def convert_currency(amount: float, from_curr: str, to_curr: str) -> Dict:
        """تحويل العملات المتقدم"""
        try:
            # استخدام API حقيقي أو بيانات افتراضية
            rates = {
                "USD": 1.0,
                "SAR": 3.75,
                "EUR": 0.92,
                "GBP": 0.79,
                "AED": 3.67,
                "QAR": 3.64,
                "KWD": 0.31,
                "OMR": 0.38,
                "BHD": 0.38
            }
            
            if from_curr.upper() in rates and to_curr.upper() in rates:
                converted = amount * (rates[to_curr.upper()] / rates[from_curr.upper()])
                
                return {
                    "from": {"currency": from_curr.upper(), "amount": round(amount, 2)},
                    "to": {"currency": to_curr.upper(), "amount": round(converted, 2)},
                    "rate": round(rates[to_curr.upper()] / rates[from_curr.upper()], 4),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                return {"error": "عملة غير مدعومة"}
        except Exception as e:
            logger.error(f"خطأ في تحويل العملة: {e}")
            return {"error": "خطأ في التحويل"}
    
    @staticmethod
    def convert_units(value: float, from_unit: str, to_unit: str, 
                     unit_type: str = "data") -> Optional[float]:
        """تحويل الوحدات"""
        conversion_factors = {
            "data": {
                "KB": 1024,
                "MB": 1024**2,
                "GB": 1024**3,
                "TB": 1024**4
            },
            "length": {
                "mm": 0.001,
                "cm": 0.01,
                "m": 1,
                "km": 1000
            },
            "weight": {
                "g": 1,
                "kg": 1000,
                "ton": 1000000
            },
            "temperature": {
                "C": lambda x: x,
                "F": lambda x: (x * 9/5) + 32,
                "K": lambda x: x + 273.15
            }
        }
        
        if unit_type in conversion_factors:
            if unit_type == "temperature":
                # تحويل درجات الحرارة
                conversions = {
                    ("C", "F"): lambda x: (x * 9/5) + 32,
                    ("F", "C"): lambda x: (x - 32) * 5/9,
                    ("C", "K"): lambda x: x + 273.15,
                    ("K", "C"): lambda x: x - 273.15,
                    ("F", "K"): lambda x: (x - 32) * 5/9 + 273.15,
                    ("K", "F"): lambda x: (x - 273.15) * 9/5 + 32
                }
                
                if (from_unit, to_unit) in conversions:
                    return round(conversions[(from_unit, to_unit)](value), 2)
            else:
                # تحويل وحدات عادية
                factors = conversion_factors[unit_type]
                if from_unit in factors and to_unit in factors:
                    meters = value * factors[from_unit]
                    return round(meters / factors[to_unit], 2)
        
        return None
    
    @staticmethod
    def calculate_age(birth_date: str) -> Dict:
        """حساب العمر التفصيلي"""
        try:
            birth = datetime.strptime(birth_date, "%Y-%m-%d")
            today = datetime.now()
            
            years = today.year - birth.year
            months = today.month - birth.month
            days = today.day - birth.day
            
            if days < 0:
                months -= 1
                # عدد الأيام في الشهر السابق
                prev_month = today.replace(day=1) - timedelta(days=1)
                days += prev_month.day
            
            if months < 0:
                years -= 1
                months += 12
            
            # حساب إجمالي الأيام
            total_days = (today - birth).days
            
            # حساب التواريخ المهمة
            next_birthday = birth.replace(year=today.year)
            if next_birthday < today:
                next_birthday = next_birthday.replace(year=today.year + 1)
            
            days_to_birthday = (next_birthday - today).days
            
            # العمر بالأشهر والأسابيع
            total_months = years * 12 + months
            total_weeks = total_days // 7
            
            return {
                "birth_date": birth_date,
                "current_date": today.strftime("%Y-%m-%d"),
                "age": {
                    "years": years,
                    "months": months,
                    "days": days
                },
                "total": {
                    "days": total_days,
                    "weeks": total_weeks,
                    "months": total_months
                },
                "next_birthday": {
                    "date": next_birthday.strftime("%Y-%m-%d"),
                    "in_days": days_to_birthday,
                    "weekday": next_birthday.strftime("%A")
                },
                "zodiac": DailyTools.get_zodiac_sign(birth.day, birth.month)
            }
        except Exception as e:
            logger.error(f"خطأ في حساب العمر: {e}")
            return {"error": "تاريخ غير صحيح. استخدم الصيغة: YYYY-MM-DD"}
    
    @staticmethod
    def get_zodiac_sign(day: int, month: int) -> str:
        """الحصول على البرج الفلكي"""
        zodiac_signs = [
            ("الحمل", (3, 21), (4, 19)),
            ("الثور", (4, 20), (5, 20)),
            ("الجوزاء", (5, 21), (6, 20)),
            ("السرطان", (6, 21), (7, 22)),
            ("الأسد", (7, 23), (8, 22)),
            ("العذراء", (8, 23), (9, 22)),
            ("الميزان", (9, 23), (10, 22)),
            ("العقرب", (10, 23), (11, 21)),
            ("القوس", (11, 22), (12, 21)),
            ("الجدي", (12, 22), (1, 19)),
            ("الدلو", (1, 20), (2, 18)),
            ("الحوت", (2, 19), (3, 20))
        ]
        
        for sign, (start_month, start_day), (end_month, end_day) in zodiac_signs:
            if (month == start_month and day >= start_day) or (month == end_month and day <= end_day):
                return sign
        return "غير معروف"

# ==================== نظام الألعاب ====================
class GameManager:
    """مدير الألعاب"""
    
    # لعبة XO
    class XOGame:
        def __init__(self, player_id: int):
            self.player_id = player_id
            self.board = [['' for _ in range(3)] for _ in range(3)]
            self.current_player = 'X'
            self.moves = 0
            self.start_time = datetime.now()
            self.winner = None
        
        def make_move(self, row: int, col: int) -> bool:
            """تنفيذ حركة"""
            if 0 <= row < 3 and 0 <= col < 3 and not self.board[row][col]:
                self.board[row][col] = self.current_player
                self.moves += 1
                
                # التحقق من الفوز
                if self.check_win():
                    self.winner = self.current_player
                
                # تبديل اللاعب
                self.current_player = 'O' if self.current_player == 'X' else 'X'
                return True
            return False
        
        def check_win(self) -> bool:
            """التحقق من الفوز"""
            # الصفوف
            for row in self.board:
                if row[0] == row[1] == row[2] != '':
                    return True
            
            # الأعمدة
            for col in range(3):
                if self.board[0][col] == self.board[1][col] == self.board[2][col] != '':
                    return True
            
            # الأقطار
            if self.board[0][0] == self.board[1][1] == self.board[2][2] != '':
                return True
            if self.board[0][2] == self.board[1][1] == self.board[2][0] != '':
                return True
            
            return False
        
        def is_draw(self) -> bool:
            """التحقق من التعادل"""
            return self.moves == 9 and not self.winner
        
        def get_board_text(self) -> str:
            """الحصول على اللوحة كنص"""
            symbols = {'X': '❌', 'O': '⭕', '': '⬜'}
            board_text = ""
            for row in self.board:
                board_text += ''.join([symbols[cell] for cell in row]) + '\n'
            return board_text
    
    # تخزين الألعاب النشطة
    active_games = {}
    
    @classmethod
    def start_xo_game(cls, user_id: int):
        """بدء لعبة XO جديدة"""
        game = cls.XOGame(user_id)
        cls.active_games[user_id] = game
        return game
    
    @classmethod
    def get_xo_game(cls, user_id: int):
        """الحصول على لعبة XO نشطة"""
        return cls.active_games.get(user_id)
    
    @classmethod
    def end_xo_game(cls, user_id: int):
        """إنهاء لعبة XO"""
        if user_id in cls.active_games:
            del cls.active_games[user_id]
    
    @staticmethod
    def number_guessing_game(user_id: int, guess: int) -> Dict:
        """لعبة تخمين الأرقام"""
        # الحصول على الرقم السري من قاعدة البيانات أو إنشائه
        db.cursor.execute(
            "SELECT game_data FROM games WHERE user_id = ? AND game_type = 'number_guess' ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        row = db.cursor.fetchone()
        
        if row:
            game_data = json.loads(row[0])
            secret_number = game_data.get("secret_number")
        else:
            secret_number = random.randint(1, 100)
            game_data = {"secret_number": secret_number, "attempts": 0}
        
        attempts = game_data.get("attempts", 0) + 1
        
        # المقارنة
        if guess == secret_number:
            points = max(20 - attempts, 5)  # نقاط أقل مع المحاولات الأكثر
            status = "win"
            message = f"🎉 مبروك! لقد خمنت الرقم الصحيح {secret_number} في {attempts} محاولة!"
        elif guess < secret_number:
            points = 0
            status = "low"
            message = f"📈 الرقم أكبر من {guess}. حاول مرة أخرى!"
        else:
            points = 0
            status = "high"
            message = f"📉 الرقم أصغر من {guess}. حاول مرة أخرى!"
        
        # حفظ حالة اللعبة
        game_data["attempts"] = attempts
        game_data["last_guess"] = guess
        game_data["last_result"] = status
        
        db.cursor.execute(
            """INSERT INTO games (user_id, game_type, score, points_earned, duration) 
            VALUES (?, ?, ?, ?, ?)""",
            (user_id, "number_guess", attempts, points, 0)
        )
        
        # إذا فاز، إنشاء رقم جديد
        if status == "win":
            secret_number = random.randint(1, 100)
            game_data = {"secret_number": secret_number, "attempts": 0}
        
        # حفظ في قاعدة البيانات (كبيانات إضافية)
        game_data_json = json.dumps(game_data)
        
        return {
            "status": status,
            "message": message,
            "points": points,
            "attempts": attempts,
            "secret_number": secret_number if status == "win" else None
        }
    
    @staticmethod
    def quiz_game(user_id: int) -> Dict:
        """لعبة الأسئلة"""
        questions = Config.GAMES["quiz_questions"]
        question = random.choice(questions)
        
        return {
            "question": question["question"],
            "answer": question["answer"],
            "points": 5
        }
    
    @staticmethod
    def check_quiz_answer(user_id: int, question: str, user_answer: str) -> bool:
        """التحقق من إجابة السؤال"""
        for q in Config.GAMES["quiz_questions"]:
            if q["question"] == question:
                return user_answer.strip().lower() == q["answer"].lower()
        return False

# ==================== معالجات البوت ====================
class BotHandlers:
    """جميع معالجات البوت"""
    
    # حالات المحادثة
    (WAITING_FOR_PDF_TEXT, WAITING_FOR_TOOL_INPUT, WAITING_FOR_GAME_INPUT,
     WAITING_FOR_ADMIN_BROADCAST, WAITING_FOR_ADMIN_ADD_POINTS) = range(5)
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة أمر /start"""
        user = update.effective_user
        logger.info(f"مستخدم جديد: {user.id} - {user.username}")
        
        # التحقق من وجود محيل
        referred_by = None
        if context.args:
            referral_code = context.args[0]
            db.cursor.execute(
                "SELECT user_id FROM users WHERE referral_code = ?",
                (referral_code,)
            )
            row = db.cursor.fetchone()
            if row:
                referred_by = row[0]
        
        # التحقق من وجود المستخدم
        user_data = db.get_user(user.id)
        
        if not user_data:
            # إنشاء مستخدم جديد
            user_data = db.create_user(
                user.id, 
                user.username or "", 
                user.first_name, 
                user.last_name or "",
                referred_by
            )
            
            welcome_message = f"""
            🎉 **أهلاً وسهلاً بك {user.first_name}!**
            
            🤖 **بوت خدمات رقمية متكامل**
            📊 **بنظام النقاط المميز**
            
            🎁 **لقد حصلت على {Config.POINTS['welcome']} نقطة ترحيبية!**
            
            💎 **اكسب نقاط عن طريق:**
            • 👀 مشاهدة الإعلانات
            • 👥 إحالة الأصدقاء
            • 🎮 لعب الألعاب
            • 🎁 المكافأة اليومية
            
            📝 **الخدمات المتاحة:**
            • 📄 تحويل النصوص إلى PDF
            • 🛠️ أدوات يومية مجانية
            • 🎮 ألعاب تفاعلية
            • 💰 نظام نقاط متكامل
            
            استخدم الأزرار أدناه للتنقل 👇
            """
        else:
            welcome_message = f"""
            👋 **مرحباً بعودتك {user.first_name}!**
            
            💰 **رصيدك الحالي:** {user_data['points']} نقطة
            
            استخدم الأزرار أدناه للوصول للخدمات 👇
            """
        
        # لوحة المفاتيح الرئيسية
        keyboard = [
            [InlineKeyboardButton("💰 نقاطي والإحالة", callback_data="points_menu")],
            [
                InlineKeyboardButton("📄 تحويل PDF", callback_data="pdf_menu"),
                InlineKeyboardButton("🛠️ أدوات يومية", callback_data="tools_menu")
            ],
            [
                InlineKeyboardButton("🎮 الألعاب", callback_data="games_menu"),
                InlineKeyboardButton("👀 الإعلانات", callback_data="ads_menu")
            ]
        ]
        
        # إضافة زر المشرف إذا كان مستخدمًا
        if user.id in Config.ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 لوحة المشرف", callback_data="admin_menu")])
        
        keyboard.append([InlineKeyboardButton("❓ المساعدة", callback_data="help_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الصورة الترحيبية (اختياري)
        try:
            await update.message.reply_photo(
                photo="https://via.placeholder.com/400x200/4A90E2/FFFFFF?text=Malik+Services+Bot",
                caption=welcome_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text(
                welcome_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        # تحديث الإحصائيات
        db.update_daily_stats()
        
        return ConversationHandler.END
    
    @staticmethod
    async def points_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة النقاط"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ لم يتم العثور على حسابك. استخدم /start أولاً")
            return
        
        stats = db.get_user_stats(user.id)
        
        message = f"""
        💰 **رصيد النقاط والإحالة**
        
        👤 **المستخدم:** {user_data['first_name']}
        🆔 **ID:** `{user_data['user_id']}`
        
        ⭐ **النقاط الحالية:** `{user_data['points']}`
        📊 **نقاط اليوم:** `{stats['today_points']}`
        📈 **نقاط الأسبوع:** `{stats['week_points']}`
        
        👥 **الإحالات:** `{stats.get('referrals_count', 0)}`
        🏆 **الترتيب:** `#{stats.get('rank', 0)}`
        
        💎 **كسب المزيد:**
        • 👀 مشاهدة إعلان (+{Config.POINTS['ad_view']} نقطة)
        • 👥 إحالة صديق (+{Config.POINTS['referral']} نقطة لكل صديق)
        • 🎮 ألعاب (+{Config.POINTS['game_min']}-{Config.POINTS['game_max']} نقطة)
        • 🎁 المكافأة اليومية (+{Config.POINTS['daily_min']}-{Config.POINTS['daily_max']} نقطة)
        
        📥 **كود الإحالة:** `{user_data['referral_code']}`
        🔗 **رابط الإحالة:** `https://t.me/{(await context.bot.get_me()).username}?start={user_data['referral_code']}`
        """
        
        keyboard = [
            [
                InlineKeyboardButton("👀 مشاهدة إعلان", callback_data="view_ad"),
                InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily_reward")
            ],
            [
                InlineKeyboardButton("👥 مشاركة الإحالة", callback_data="share_referral"),
                InlineKeyboardButton("📋 سجل المعاملات", callback_data="transactions_history")
            ],
            [
                InlineKeyboardButton("🏆 لوحة المتصدرين", callback_data="leaderboard"),
                InlineKeyboardButton("💳 طلب سحب", callback_data="withdraw_request")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def daily_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """المكافأة اليومية"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ لم يتم العثور على حسابك")
            return
        
        # التحقق من المكافأة اليومية
        can_claim, remaining_time = BotHandlers.check_daily_reward(user_data)
        
        if not can_claim:
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            seconds = remaining_time % 60
            
            await query.edit_message_text(
                f"⏳ **المكافأة اليومية**\n\n"
                f"لقد حصلت على المكافأة اليومية بالفعل!\n"
                f"⏰ عد بعد: {hours:02d}:{minutes:02d}:{seconds:02d}\n\n"
                f"💰 رصيدك الحالي: {user_data['points']} نقطة",
                parse_mode='Markdown'
            )
            return
        
        # منح المكافأة
        reward = random.randint(
            Config.POINTS["daily_min"],
            Config.POINTS["daily_max"]
        )
        
        db.add_points(
            user.id,
            reward,
            "daily",
            "المكافأة اليومية"
        )
        
        # تحديث وقت المكافأة
        db.update_user(user.id, last_daily=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # الحصول على الرصيد الجديد
        user_data = db.get_user(user.id)
        
        message = f"""
        🎁 **المكافأة اليومية**
        
        🎉 مبروك! لقد حصلت على مكافأتك اليومية!
        
        💰 **المكافأة:** +{reward} نقطة
        📊 **رصيدك الجديد:** {user_data['points']} نقطة
        
        ⏳ عد بعد 24 ساعة لمكافأة جديدة!
        
        💡 **نصيحة:** يمكنك كسب المزيد عن طريق:
        • مشاهدة الإعلانات
        • إحالة الأصدقاء
        • لعب الألعاب
        """
        
        keyboard = [
            [
                InlineKeyboardButton("👀 مشاهدة إعلان", callback_data="view_ad"),
                InlineKeyboardButton("🎮 لعب ألعاب", callback_data="games_menu")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="points_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def view_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مشاهدة إعلان"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ لم يتم العثور على حسابك")
            return
        
        # التحقق من الوقت بين الإعلانات
        can_view, remaining_time = BotHandlers.check_ad_cooldown(user_data)
        
        if not can_view:
            minutes = remaining_time // 60
            seconds = remaining_time % 60
            
            await query.edit_message_text(
                f"⏳ **مشاهدة الإعلانات**\n\n"
                f"يمكنك مشاهدة إعلان آخر بعد:\n"
                f"⏰ {minutes:02d}:{seconds:02d}\n\n"
                f"💰 رصيدك الحالي: {user_data['points']} نقطة",
                parse_mode='Markdown'
            )
            return
        
        # الحصول على إعلان
        ad = db.get_available_ad(user.id)
        
        if not ad:
            await query.edit_message_text(
                "📢 **لا توجد إعلانات متاحة حالياً**\n\n"
                "عد لاحقاً لمشاهدة إعلانات جديدة!",
                parse_mode='Markdown'
            )
            return
        
        # بناء رسالة الإعلان
        ad_message = f"""
        📢 **{ad['title']}**
        
        {ad['content']}
        
        💰 **المكافأة:** +{ad.get('points', Config.POINTS['ad_view'])} نقطة
        
        """
        
        if ad.get('link'):
            ad_message += f"🔗 [رابط الإعلان]({ad['link']})\n\n"
        
        ad_message += f"انقر على زر ✅ بعد المشاهدة"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ شاهدت الإعلان", callback_data=f"ad_watched_{ad['id']}"),
                InlineKeyboardButton("🔗 زيارة الرابط", url=ad['link']) if ad.get('link') else None
            ],
            [InlineKeyboardButton("🚫 تخطي الإعلان", callback_data="ads_menu")]
        ]
        
        # إزالة الأزرار الفارغة
        keyboard = [row for row in keyboard if any(row)]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الإعلان حسب نوعه
        try:
            if ad.get('image_url'):
                await query.edit_message_media(
                    media=InputMediaPhoto(
                        media=ad['image_url'],
                        caption=ad_message,
                        parse_mode='Markdown'
                    ),
                    reply_markup=reply_markup
                )
            elif ad.get('video_url'):
                await query.edit_message_media(
                    media=InputMediaVideo(
                        media=ad['video_url'],
                        caption=ad_message,
                        parse_mode='Markdown'
                    ),
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    ad_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"خطأ في عرض الإعلان: {e}")
            await query.edit_message_text(
                ad_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def ad_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تمت مشاهدة الإعلان"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        ad_id = int(query.data.split('_')[-1])
        
        # تسجيل مشاهدة الإعلان
        ad = db.cursor.execute(
            "SELECT * FROM ads WHERE id = ?",
            (ad_id,)
        ).fetchone()
        
        if ad:
            ad = dict(ad)
            points = ad.get('points', Config.POINTS['ad_view'])
            
            # منح النقاط
            db.add_points(user.id, points, "ad_view", f"مشاهدة إعلان: {ad['title']}")
            
            # تسجيل المشاهدة
            db.record_ad_view(user.id, ad_id, clicked=False)
            
            # تحديث وقت آخر إعلان
            db.update_user(user.id, last_ad=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # الحصول على الرصيد الجديد
            user_data = db.get_user(user.id)
            
            message = f"""
            ✅ **شكراً لمشاهدة الإعلان**
            
            🎁 **تمت إضافة {points} نقطة إلى رصيدك!**
            
            💰 **رصيدك الجديد:** {user_data['points']} نقطة
            
            📢 **عنوان الإعلان:** {ad['title']}
            
            ⏳ يمكنك مشاهدة إعلان آخر بعد 5 دقائق
            """
        else:
            message = "❌ عذراً، حدث خطأ في معالجة الإعلان"
        
        keyboard = [
            [InlineKeyboardButton("👀 إعلان آخر", callback_data="view_ad")],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def pdf_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة خدمات PDF"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ لم يتم العثور على حسابك")
            return
        
        message = f"""
        📄 **خدمات تحويل ومعالجة PDF**
        
        💰 **رصيدك الحالي:** {user_data['points']} نقطة
        
        **الخدمات المتاحة:**
        
        📝 **تحويل نص إلى PDF**
        • تكلفة: {Config.POINTS['pdf_conversion']} نقطة
        • الحد الأقصى: {Config.PDF_SETTINGS['max_text_length']} حرف
        
        🔗 **دمج ملفات PDF**
        • تكلفة: {Config.POINTS['pdf_merge']} نقطة لكل ملف
        • الحد الأقصى: 5 ملفات
        
        📉 **ضغط ملف PDF**
        • تكلفة: {Config.POINTS['pdf_compress']} نقطة
        • تقليل الحجم حتى 70%
        
        🔢 **معرفة معلومات PDF**
        • مجاناً
        • عدد الصفحات، الحجم، وغيرها
        
        **للتحويل:** اختر الخدمة ثم أرسل النص أو الملف
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📝 نص إلى PDF", callback_data="pdf_text"),
                InlineKeyboardButton("🔗 دمج PDF", callback_data="pdf_merge")
            ],
            [
                InlineKeyboardButton("📉 ضغط PDF", callback_data="pdf_compress"),
                InlineKeyboardButton("🔢 معلومات PDF", callback_data="pdf_info")
            ],
            [
                InlineKeyboardButton("📋 سجل الملفات", callback_data="pdf_history"),
                InlineKeyboardButton("⚙️ إعدادات", callback_data="pdf_settings")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def pdf_text_conversion(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تحويل نص إلى PDF"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ لم يتم العثور على حسابك")
            return
        
        # التحقق من الرصيد
        if user_data['points'] < Config.POINTS['pdf_conversion']:
            await query.edit_message_text(
                f"❌ **نقاطك غير كافية**\n\n"
                f"تحتاج {Config.POINTS['pdf_conversion']} نقطة\n"
                f"رصيدك الحالي: {user_data['points']} نقطة\n\n"
                f"💡 اكسب نقاط عن طريق:\n"
                f"• مشاهدة الإعلانات\n"
                f"• إحالة الأصدقاء\n"
                f"• المكافأة اليومية",
                parse_mode='Markdown'
            )
            return
        
        await query.edit_message_text(
            "📝 **تحويل نص إلى PDF**\n\n"
            "أرسل النص الذي تريد تحويله الآن...\n\n"
            f"💰 **التكلفة:** {Config.POINTS['pdf_conversion']} نقطة\n"
            f"📏 **الحد الأقصى:** {Config.PDF_SETTINGS['max_text_length']} حرف\n\n"
            "💡 **نصائح:**\n"
            "• استخدم النصوص العربية أو الإنجليزية\n"
            "• يمكنك إرسال نصوص طويلة\n"
            "• اضغط /cancel للإلغاء"
        )
        
        return BotHandlers.WAITING_FOR_PDF_TEXT
    
    @staticmethod
    async def handle_pdf_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة نص PDF"""
        user = update.effective_user
        text = update.message.text
        
        # التحقق من طول النص
        if len(text) > Config.PDF_SETTINGS['max_text_length']:
            await update.message.reply_text(
                f"❌ النص طويل جداً!\n"
                f"الحد الأقصى: {Config.PDF_SETTINGS['max_text_length']} حرف\n"
                f"طول نصك: {len(text)} حرف\n\n"
                f"💡 قسم النص إلى أجزاء أصغر"
            )
            return BotHandlers.WAITING_FOR_PDF_TEXT
        
        user_data = db.get_user(user.id)
        
        # خصم النقاط
        if not db.deduct_points(
            user.id,
            Config.POINTS['pdf_conversion'],
            "pdf_conversion",
            "تحويل نص إلى PDF"
        ):
            await update.message.reply_text("❌ خطأ في خصم النقاط!")
            return ConversationHandler.END
        
        # إظهار رسالة المعالجة
        processing_msg = await update.message.reply_text(
            "⏳ جاري تحويل النص إلى PDF...\n"
            "قد تستغرق العملية بضع ثوانٍ"
        )
        
        try:
            # تحويل النص إلى PDF
            pdf_manager = PDFManager()
            pdf_file = pdf_manager.text_to_pdf(
                text,
                f"document_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                Config.PDF_SETTINGS['default_font_size'],
                Config.PDF_SETTINGS['default_margin']
            )
            
            # تسجيل الملف في قاعدة البيانات
            db.cursor.execute(
                """INSERT INTO files 
                (user_id, file_name, file_type, file_size, operation_type, points_cost) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user.id, f"document_{user.id}.pdf", "pdf", 
                 len(pdf_file.getvalue()), "text_to_pdf", Config.POINTS['pdf_conversion'])
            )
            db.conn.commit()
            
            # حذف رسالة المعالجة
            await processing_msg.delete()
            
            # إرسال الملف
            await update.message.reply_document(
                document=InputFile(pdf_file, filename=f"مستند_{user.first_name}.pdf"),
                caption=f"✅ **تم تحويل النص إلى PDF بنجاح!**\n\n"
                       f"📄 **اسم الملف:** مستند_{user.first_name}.pdf\n"
                       f"📏 **حجم الملف:** {len(pdf_file.getvalue()) / 1024:.1f} كيلوبايت\n"
                       f"💰 **التكلفة:** {Config.POINTS['pdf_conversion']} نقطة\n"
                       f"💎 **رصيدك الجديد:** {user_data['points'] - Config.POINTS['pdf_conversion']} نقطة\n\n"
                       f"شكراً لاستخدامك خدماتنا!",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"خطأ في تحويل PDF: {e}")
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء التحويل**\n\n"
                "عذراً، حدث خطأ غير متوقع.\n"
                "تم إرجاع نقاطك.\n\n"
                "يرجى المحاولة مرة أخرى لاحقاً."
            )
            
            # إرجاع النقاط
            db.add_points(user.id, Config.POINTS['pdf_conversion'], "refund", "استرجاع نقاط تحويل PDF فاشل")
        
        return ConversationHandler.END
    
    @staticmethod
    async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة الأدوات اليومية"""
        query = update.callback_query
        await query.answer()
        
        message = """
        🛠️ **الأدوات اليومية المجانية**
        
        **اختر الأداة التي تحتاجها:**
        
        🧾 **حاسبة الأقساط**
        • احسب أقساط القروض
        • مع الفوائد والمدة
        
        💰 **حاسبة الأرباح**
        • احسب أرباح الاستثمارات
        • فائدة بسيطة ومركبة
        
        💱 **تحويل العملات**
        • بين جميع العملات العالمية
        • أسعار محدثة
        
        📏 **تحويل الوحدات**
        • بيانات: KB, MB, GB, TB
        • أطوال: سم, متر, كيلومتر
        • أوزان: جرام, كيلو, طن
        • حرارة: مئوية, فهرنهايت
        
        ⏰ **حساب العمر**
        • احسب عمرك بالتفصيل
        • تاريخ الميلاد القادم
        • البرج الفلكي
        
        📅 **حساب التاريخ**
        • أضف أو اطرح أيام
        • احسب الفرق بين تاريخين
        
        🎲 **أدوات عشوائية**
        • توليد أرقام عشوائية
        • اختيار عشوائي من قائمة
        • عملة عشوائية
        
        **جميع الأدوات مجانية!** 🎉
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🧾 حاسبة الأقساط", callback_data="tool_installment"),
                InlineKeyboardButton("💰 حاسبة الأرباح", callback_data="tool_profit")
            ],
            [
                InlineKeyboardButton("💱 تحويل عملات", callback_data="tool_currency"),
                InlineKeyboardButton("📏 تحويل وحدات", callback_data="tool_units")
            ],
            [
                InlineKeyboardButton("⏰ حساب العمر", callback_data="tool_age"),
                InlineKeyboardButton("📅 حساب التاريخ", callback_data="tool_date")
            ],
            [
                InlineKeyboardButton("🎲 أدوات عشوائية", callback_data="tool_random"),
                InlineKeyboardButton("🔢 آلة حاسبة", callback_data="tool_calculator")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def tool_installment_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """حاسبة الأقساط"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "🧾 **حاسبة الأقساط**\n\n"
            "أرسل بيانات القرض بالصيغة التالية:\n\n"
            "`المبلغ, المدة بالأشهر, نسبة الفائدة`\n\n"
            "**مثال:**\n"
            "`10000, 12, 5`\n\n"
            "💡 **تفسير المثال:**\n"
            "• قرض 10,000 ريال\n"
            "• لمدة 12 شهر\n"
            "• بنسبة فائدة 5%\n\n"
            "اضغط /cancel للإلغاء"
        )
        
        context.user_data['tool'] = 'installment'
        return BotHandlers.WAITING_FOR_TOOL_INPUT
    
    @staticmethod
    async def handle_tool_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة إدخال الأداة"""
        user = update.effective_user
        user_input = update.message.text
        
        tool_type = context.user_data.get('tool')
        
        if tool_type == 'installment':
            try:
                # تحليل الإدخال
                parts = [p.strip() for p in user_input.split(',')]
                if len(parts) != 3:
                    raise ValueError
                
                amount = float(parts[0])
                months = int(parts[1])
                interest = float(parts[2])
                
                # التحقق من القيم
                if amount <= 0 or months <= 0 or interest < 0:
                    raise ValueError
                
                # الحساب
                tools = DailyTools()
                result = tools.calculate_installment(amount, months, interest)
                
                if not result:
                    raise ValueError
                
                # بناء النتيجة
                response = f"""
                🧾 **نتيجة حساب الأقساط**
                
                💰 **المبلغ:** {result['amount']:,} ريال
                📅 **المدة:** {result['months']} شهر
                📈 **نسبة الفائدة:** {result['interest_rate']}%
                
                **النتائج:**
                
                💳 **القسط الشهري:** {result['monthly_payment']:,} ريال
                💵 **إجمالي السداد:** {result['total_payment']:,} ريال
                📊 **إجمالي الفائدة:** {result['total_interest']:,} ريال
                
                **جدول السداد (أول 6 أشهر):**
                """
                
                for payment in result['payment_schedule'][:6]:
                    response += f"\nالشهر {payment['month']}: {payment['payment']:,} ريال - المتبقي: {payment['remaining']:,} ريال"
                
                if len(result['payment_schedule']) > 6:
                    response += f"\n\n... وهكذا حتى الشهر {months}"
                
                response += "\n\n💡 *ملاحظة:* هذه حسابات تقريبية وقد تختلف قليلاً في التطبيق العملي."
                
                await update.message.reply_text(
                    response,
                    parse_mode='Markdown'
                )
                
            except ValueError:
                await update.message.reply_text(
                    "❌ **إدخال غير صحيح!**\n\n"
                    "يرجى إدخال البيانات بالصيغة الصحيحة:\n"
                    "`المبلغ, المدة بالأشهر, نسبة الفائدة`\n\n"
                    "**مثال صحيح:** `10000, 12, 5`\n\n"
                    "💡 **ملاحظات:**\n"
                    "• استخدم الأرقام فقط\n"
                    "• الفواصل يجب أن تكون باللغة الإنجليزية\n"
                    "• نسبة الفائدة يمكن أن تكون 0"
                )
                return BotHandlers.WAITING_FOR_TOOL_INPUT
        
        elif tool_type == 'currency':
            try:
                parts = [p.strip() for p in user_input.split(',')]
                if len(parts) != 3:
                    raise ValueError
                
                amount = float(parts[0])
                from_curr = parts[1].upper()
                to_curr = parts[2].upper()
                
                # التحقق من العملات
                if from_curr not in Config.CURRENCIES or to_curr not in Config.CURRENCIES:
                    await update.message.reply_text(
                        f"❌ **عملة غير مدعومة!**\n\n"
                        f"العملات المدعومة: {', '.join(Config.CURRENCIES)}\n\n"
                        f"**مثال صحيح:** `100, USD, SAR`"
                    )
                    return BotHandlers.WAITING_FOR_TOOL_INPUT
                
                # التحويل
                tools = DailyTools()
                result = tools.convert_currency(amount, from_curr, to_curr)
                
                if 'error' in result:
                    await update.message.reply_text(f"❌ {result['error']}")
                    return BotHandlers.WAITING_FOR_TOOL_INPUT
                
                response = f"""
                💱 **نتيجة تحويل العملة**
                
                💵 **من:** {result['from']['amount']:,} {result['from']['currency']}
                💰 **إلى:** {result['to']['amount']:,} {result['to']['currency']}
                
                📊 **سعر الصرف:** 1 {from_curr} = {result['rate']} {to_curr}
                🕐 **الوقت:** {result['timestamp']}
                
                💡 *ملاحظة:* الأسعار تقريبية وقد تختلف عن الأسعار الفعلية في السوق.
                """
                
                await update.message.reply_text(
                    response,
                    parse_mode='Markdown'
                )
                
            except ValueError:
                await update.message.reply_text(
                    "❌ **إدخال غير صحيح!**\n\n"
                    "يرجى إدخال البيانات بالصيغة الصحيحة:\n"
                    "`المبلغ, العملة الأصلية, العملة الهدف`\n\n"
                    "**مثال صحيح:** `100, USD, SAR`\n\n"
                    f"💡 **العملات المدعومة:** {', '.join(Config.CURRENCIES)}"
                )
                return BotHandlers.WAITING_FOR_TOOL_INPUT
        
        # إضافة المزيد من الأدوات هنا...
        
        return ConversationHandler.END
    
    @staticmethod
    async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة الألعاب"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ لم يتم العثور على حسابك")
            return
        
        message = f"""
        🎮 **قاعة الألعاب**
        
        💰 **رصيدك الحالي:** {user_data['points']} نقطة
        
        **الألعاب المتاحة:**
        
        🎲 **تخمين الأرقام**
        • خمن الرقم بين 1 و 100
        • مكافأة: 5-20 نقطة
        
        ❌⭕ **لعبة XO**
        • ضد الذكاء الاصطناعي
        • مكافأة الفوز: 10 نقطة
        
        ❓ **لعبة الأسئلة**
        • أسئلة عامة
        • مكافأة الإجابة الصحيحة: 5 نقطة
        
        🎯 **لعبة الرياضيات**
        • مسائل حسابية سريعة
        • مكافأة: 2-10 نقاط
        
        🃏 **لعبة الورق**
        • ضد الذكاء الاصطناعي
        • مكافأة الفوز: 15 نقطة
        
        🎁 **المكافأة اليومية**
        • احصل على نقاط مجانية
        • مرة كل 24 ساعة
        
        **المكافآت:** {Config.POINTS['game_min']}-{Config.POINTS['game_max']} نقطة لكل لعبة
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🎲 تخمين الأرقام", callback_data="game_numbers"),
                InlineKeyboardButton("❌⭕ لعبة XO", callback_data="game_xo")
            ],
            [
                InlineKeyboardButton("❓ لعبة الأسئلة", callback_data="game_quiz"),
                InlineKeyboardButton("🎯 لعبة الرياضيات", callback_data="game_math")
            ],
            [
                InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily_reward"),
                InlineKeyboardButton("🏆 إحصائيات الألعاب", callback_data="game_stats")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def number_guessing_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لعبة تخمين الأرقام"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "🎲 **لعبة تخمين الأرقام**\n\n"
            "أرسل رقم بين 1 و 100:\n\n"
            "💡 **القواعد:**\n"
            "• اختر رقم بين 1 و 100\n"
            "• سأخبرك إذا كان الرقم أكبر أو أصغر\n"
            "• كل محاولة تقلّل من مكافأتك النهائية\n"
            "• المكافأة القصوى: 20 نقطة\n\n"
            "اكتب رقمك الآن...\n"
            "اضغط /cancel للإلغاء"
        )
        
        context.user_data['game'] = 'number_guess'
        return BotHandlers.WAITING_FOR_GAME_INPUT
    
    @staticmethod
    async def handle_game_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة إدخال اللعبة"""
        user = update.effective_user
        user_input = update.message.text
        
        game_type = context.user_data.get('game')
        
        if game_type == 'number_guess':
            try:
                guess = int(user_input)
                
                if not (1 <= guess <= 100):
                    await update.message.reply_text(
                        "❌ **الرقم خارج النطاق!**\n\n"
                        "يرجى إدخال رقم بين 1 و 100"
                    )
                    return BotHandlers.WAITING_FOR_GAME_INPUT
                
                # تشغيل اللعبة
                result = GameManager.number_guessing_game(user.id, guess)
                
                if result['status'] == 'win':
                    # منح النقاط
                    db.add_points(
                        user.id,
                        result['points'],
                        "game",
                        f"فوز بلعبة تخمين الأرقام ({result['attempts']} محاولات)"
                    )
                    
                    response = f"""
                    {result['message']}
                    
                    🎁 **المكافأة:** +{result['points']} نقطة
                    
                    💰 **للعب مرة أخرى:** اختر رقم جديد بين 1 و 100
                    """
                    
                    keyboard = [
                        [InlineKeyboardButton("🎲 العب مرة أخرى", callback_data="game_numbers")],
                        [InlineKeyboardButton("🔙 قائمة الألعاب", callback_data="games_menu")]
                    ]
                    
                    await update.message.reply_text(
                        response,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                    
                    return ConversationHandler.END
                    
                else:
                    response = f"""
                    {result['message']}
                    
                    💡 **المحاولة:** {result['attempts']}
                    
                    **أرسل رقم آخر...**
                    """
                    
                    await update.message.reply_text(
                        response,
                        parse_mode='Markdown'
                    )
                    
                    return BotHandlers.WAITING_FOR_GAME_INPUT
                
            except ValueError:
                await update.message.reply_text(
                    "❌ **إدخال غير صحيح!**\n\n"
                    "يرجى إدخال رقم صحيح بين 1 و 100\n\n"
                    "**مثال:** `50`"
                )
                return BotHandlers.WAITING_FOR_GAME_INPUT
        
        return ConversationHandler.END
    
    @staticmethod
    async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لوحة المشرف"""
        query = update.callback_query if hasattr(update, 'callback_query') else None
        
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            if query:
                await query.answer("❌ هذا الأمر للمشرفين فقط!", show_alert=True)
            else:
                await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
            return
        
        # إحصائيات النظام
        stats = db.get_system_stats()
        
        message = f"""
        👑 **لوحة مشرف - Malik Services Bot**
        
        📊 **إحصائيات النظام:**
        
        👥 **المستخدمين:** {stats.get('total_users', 0)}
        📈 **نشط اليوم:** {stats.get('active_today', 0)}
        💰 **إجمالي النقاط:** {stats.get('total_points', 0):,.2f}
        🔄 **المعاملات:** {stats.get('total_transactions', 0):,}
        📢 **مشاهدات الإعلانات:** {stats.get('total_ad_views', 0):,}
        🎮 **الألعاب:** {stats.get('total_games', 0):,}
        
        ⚙️ **حالة البوت:** 🟢 نشط
        🕐 **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        **أوامر المشرف:**
        """
        
        keyboard = [
            [
                InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users"),
                InlineKeyboardButton("💰 إدارة النقاط", callback_data="admin_points")
            ],
            [
                InlineKeyboardButton("📢 إدارة الإعلانات", callback_data="admin_ads"),
                InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton("📣 إعلان جماعي", callback_data="admin_broadcast"),
                InlineKeyboardButton("⚙️ إعدادات النظام", callback_data="admin_settings")
            ],
            [
                InlineKeyboardButton("🔄 نسخة احتياطية", callback_data="admin_backup"),
                InlineKeyboardButton("📋 السجلات", callback_data="admin_logs")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إرسال إعلان جماعي"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await query.edit_message_text("❌ هذا الأمر للمشرفين فقط!")
            return
        
        await query.edit_message_text(
            "📣 **إرسال إعلان جماعي**\n\n"
            "أرسل نص الإعلان الآن...\n\n"
            "💡 **تنسيق الإعلان:**\n"
            "يمكنك استخدام:\n"
            "• نص عادي\n"
            "• Markdown\n"
            "• مع الصور (أرسلها كملف)\n\n"
            "⏰ **معلومة:**\n"
            "سيتم إرسال الإعلان لجميع المستخدمين.\n"
            "العملية قد تستغرق عدة دقائق.\n\n"
            "اضغط /cancel للإلغاء"
        )
        
        return BotHandlers.WAITING_FOR_ADMIN_BROADCAST
    
    @staticmethod
    async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الإعلان الجماعي"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            return ConversationHandler.END
        
        broadcast_text = update.message.text
        
        # إظهار رسالة المعالجة
        processing_msg = await update.message.reply_text(
            "⏳ جاري إرسال الإعلان لجميع المستخدمين...\n"
            "قد تستغرق العملية عدة دقائق"
        )
        
        # الحصول على جميع المستخدمين
        users = db.get_all_users()
        
        success_count = 0
        failed_count = 0
        
        for user_data in users:
            try:
                await context.bot.send_message(
                    chat_id=user_data['user_id'],
                    text=broadcast_text,
                    parse_mode='Markdown'
                )
                success_count += 1
                
                # تأخير صغير لمنع rate limiting
                if success_count % 10 == 0:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"فشل إرسال إعلان لـ {user_data['user_id']}: {e}")
        
        # تحديث رسالة المعالجة
        await processing_msg.edit_text(
            f"✅ **تم إرسال الإعلان بنجاح!**\n\n"
            f"📊 **النتائج:**\n"
            f"✅ الناجح: {success_count}\n"
            f"❌ الفاشل: {failed_count}\n"
            f"📈 الإجمالي: {len(users)}\n\n"
            f"💡 **محتوى الإعلان:**\n"
            f"{broadcast_text[:100]}..."
        )
        
        # تسجيل الإعلان في قاعدة البيانات
        db.cursor.execute(
            """INSERT INTO ads 
            (title, content, ad_type, created_by) 
            VALUES (?, ?, ?, ?)""",
            ("إعلان جماعي من المشرف", broadcast_text, "text", user.id)
        )
        db.conn.commit()
        
        return ConversationHandler.END
    
    @staticmethod
    async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة المساعدة"""
        query = update.callback_query
        await query.answer()
        
        message = """
        ❓ **مساعدة - Malik Services Bot**
        
        **🤖 عن البوت:**
        بوت خدمات رقمية متكامل يقدم خدمات متنوعة مع نظام نقاط مميز.
        
        **💎 نظام النقاط:**
        • الترحيب: +5 نقاط
        • الإعلانات: +3 نقاط كل 5 دقائق
        • الإحالة: +10 نقاط لكل صديق
        • الألعاب: 2-15 نقطة حسب اللعبة
        • اليومية: 5-20 نقطة كل 24 ساعة
        
        **📄 خدمات PDF:**
        • تحويل نص إلى PDF: 0.5 نقطة
        • دمج ملفات PDF: 1.0 نقطة لكل ملف
        • ضغط PDF: 0.3 نقطة
        • معلومات PDF: مجاناً
        
        **🛠️ الأدوات اليومية:**
        • جميع الأدوات مجانية
        • حاسبات متنوعة
        • تحويل وحدات وعملات
        • أدوات تاريخ ووقت
        
        **🎮 الألعاب:**
        • تخمين الأرقام
        • لعبة XO
        • أسئلة عامة
        • رياضيات سريعة
        
        **📢 الإعلانات:**
        • مشاهدة إعلانات لكسب النقاط
        • إعلانات متنوعة
        • روابط مفيدة
        
        **👑 المشرفين:**
        • إدارة كاملة للنظام
        • إحصائيات مفصلة
        • إرسال إعلانات
        
        **📞 الدعم:**
        للاستفسارات أو المشاكل:
        • راسل المطور: @S_1S2
        • تقارير الأخطاء: /report
        
        **🔄 الأوامر الرئيسية:**
        /start - بدء البوت
        /help - هذه الرسالة
        /points - رصيد النقاط
        /pdf - خدمات PDF
        /tools - أدوات يومية
        /games - الألعاب
        /ads - الإعلانات
        
        **💡 نصائح:**
        • اكسب نقاط يومياً
        • شارك البوت مع أصدقائك
        • استخدم جميع الخدمات
        • تابع الإعلانات الجديدة
        
        **🔒 الخصوصية:**
        • نحن نحترم خصوصيتك
        • لا نشارك بياناتك
        • جميع المعاملات آمنة
        
        شكراً لاستخدامك Malik Services Bot! 🚀
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📚 الدليل الكامل", url="https://example.com/guide"),
                InlineKeyboardButton("📞 تواصل مع الدعم", url="https://t.me/S_1S2")
            ],
            [
                InlineKeyboardButton("🐛 تقرير خطأ", callback_data="report_bug"),
                InlineKeyboardButton("💡 اقتراح", callback_data="suggest_feature")
            ],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء العملية"""
        await update.message.reply_text(
            "❌ **تم الإلغاء**\n\n"
            "العملية الحالية تم إلغاؤها.\n"
            "يمكنك البدء من جديد باستخدام /start"
        )
        return ConversationHandler.END
    
    @staticmethod
    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة جميع Callback Queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # قائمة بالمعالجات
        handlers = {
            "main_menu": BotHandlers.start,
            "points_menu": BotHandlers.points_menu,
            "daily_reward": BotHandlers.daily_reward,
            "view_ad": BotHandlers.view_advertisement,
            "ads_menu": BotHandlers.view_advertisement,
            "pdf_menu": BotHandlers.pdf_menu,
            "pdf_text": BotHandlers.pdf_text_conversion,
            "tools_menu": BotHandlers.tools_menu,
            "tool_installment": BotHandlers.tool_installment_calc,
            "tool_currency": lambda u, c: BotHandlers.tool_currency_calc(u, c),
            "games_menu": BotHandlers.games_menu,
            "game_numbers": BotHandlers.number_guessing_game,
            "admin_menu": BotHandlers.admin_menu,
            "admin_broadcast": BotHandlers.admin_broadcast,
            "help_menu": BotHandlers.help_menu,
        }
        
        # معالجة ad_watched
        if data.startswith("ad_watched_"):
            await BotHandlers.ad_watched(update, context)
            return
        
        # استدعاء المعالج المناسب
        if data in handlers:
            await handlers[data](update, context)
        else:
            await query.edit_message_text(
                "❌ **زر غير معروف**\n\n"
                "هذا الزر لم يعد يعمل أو غير موجود.\n"
                "يرجى استخدام /start للبدء من جديد."
            )
    
    @staticmethod
    def check_daily_reward(user_data: Dict) -> Tuple[bool, int]:
        """التحقق من إمكانية الحصول على المكافأة اليومية"""
        if not user_data.get('last_daily'):
            return True, 0
        
        last_daily = datetime.strptime(user_data['last_daily'], '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        
        elapsed = (now - last_daily).total_seconds()
        
        if elapsed >= Config.TIME_LIMITS['daily_cooldown']:
            return True, 0
        else:
            remaining = Config.TIME_LIMITS['daily_cooldown'] - elapsed
            return False, int(remaining)
    
    @staticmethod
    def check_ad_cooldown(user_data: Dict) -> Tuple[bool, int]:
        """التحقق من إمكانية مشاهدة إعلان"""
        if not user_data.get('last_ad'):
            return True, 0
        
        last_ad = datetime.strptime(user_data['last_ad'], '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        
        elapsed = (now - last_ad).total_seconds()
        
        if elapsed >= Config.TIME_LIMITS['ad_cooldown']:
            return True, 0
        else:
            remaining = Config.TIME_LIMITS['ad_cooldown'] - elapsed
            return False, int(remaining)

# ==================== الدالة الرئيسية ====================
def main():
    """الدالة الرئيسية لتشغيل البوت"""
    
    # التحقق من التوكن
    if Config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ الرجاء تعيين BOT_TOKEN في ملف .env أو في الكود")
        print("💡 يمكنك الحصول على التوكن من @BotFather")
        return
    
    print("🚀 بدء تشغيل بوت Malik Services...")
    print(f"📊 المشرفين: {Config.ADMIN_IDS}")
    print(f"💾 قاعدة البيانات: {Config.PATHS['database']}")
    print("⏳ جاري التهيئة...")
    
    # إنشاء التطبيق
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # محادثات متقدمة
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", BotHandlers.start),
            CallbackQueryHandler(BotHandlers.handle_callback)
        ],
        states={
            BotHandlers.WAITING_FOR_PDF_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, BotHandlers.handle_pdf_text)
            ],
            BotHandlers.WAITING_FOR_TOOL_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, BotHandlers.handle_tool_input)
            ],
            BotHandlers.WAITING_FOR_GAME_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, BotHandlers.handle_game_input)
            ],
            BotHandlers.WAITING_FOR_ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, BotHandlers.handle_admin_broadcast)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", BotHandlers.cancel),
            CommandHandler("start", BotHandlers.start)
        ],
        allow_reentry=True
    )
    
    # إضافة handlers
    application.add_handler(conv_handler)
    
    # أوامر مباشرة
    application.add_handler(CommandHandler("help", BotHandlers.help_menu))
    application.add_handler(CommandHandler("admin", BotHandlers.admin_menu, filters.User(Config.ADMIN_IDS)))
    
    # معالجة Callback Queries
    application.add_handler(CallbackQueryHandler(BotHandlers.handle_callback))
    
    # بدء البوت
    print("✅ البوت جاهز للتشغيل!")
    print("📱 اذهب إلى تيليجرام وجرب البوت الآن!")
    
    # تشغيل البوت
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )

# ==================== تشغيل البرنامج ====================
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}", exc_info=True)
        print(f"❌ خطأ غير متوقع: {e}")
        print("💡 تأكد من:\n1. صحة التوكن\n2. اتصال الإنترنت\n3. المكتبات المثبتة")
    finally:
        # إغلاق قاعدة البيانات
        if 'db' in globals():
            db.close()
        print("✅ تم إنهاء البرنامج بنجاح")
