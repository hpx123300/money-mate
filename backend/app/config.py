"""配置模块：所有配置从环境变量读取，代码里不出现密钥。"""

import os
import secrets

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Settings:
    def __init__(self):
        self.app_env = os.getenv("APP_ENV", "dev")
        self.secret_key = os.getenv("APP_SECRET_KEY", "")
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(32)  # 仅开发环境临时生成
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        # 默认数据库放在项目 data/ 目录，保持仓库整洁
        default_db = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'moneymate.db')}"
        self.database_url = os.getenv("DATABASE_URL", default_db)


settings = Settings()
