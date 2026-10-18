"""pytest 公共配置：在收集任何测试模块之前把环境固定下来。

为什么放在 conftest.py 而不是各个测试文件里：
pytest 会先导入 conftest，再收集测试模块。而 app.config 里的 settings 是
模块级单例，第一次 import 就把环境变量读死了。如果只在某个测试文件里设置
环境变量，一旦另一个测试文件先被收集（比如它 import 了 app 下的模块），
settings 就会用默认值初始化，测试可能连到开发库上。
统一在这里设置，收集顺序就不再影响结果。
"""

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# 测试专用数据库，不污染开发数据
_TMP_DB = Path(tempfile.gettempdir()) / "youshu_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["APP_ENV"] = "test"
# 不真调大模型，AI 接口的测试自行 mock
os.environ["LLM_API_KEY"] = ""
# 强制走内存缓存：限流用例要可复现，不能受本机 Redis 状态影响
os.environ["REDIS_URL"] = ""
