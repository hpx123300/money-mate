# 大学生记账助手（Hugging Face 部署说明）

1. 在 https://huggingface.co/new-space 创建 Space：
   - Space name: `moneymate`
   - License: MIT
   - SDK: Docker
2. 在 Space 的 Files 页面按下面结构上传/推送：
   - `Dockerfile` ← 使用仓库里的 `deploy/hf-spaces.Dockerfile` 内容
   - `backend/`、`frontend/`、`docs/`、`data/` 等仓库文件
3. 等待构建完成，访问 `https://huggingface.co/spaces/你的用户名/moneymate`

注意：SQLite 数据在 Space 重启后会重置（免费档没有持久化磁盘），
适合演示；正式使用建议换云服务器或外部数据库。
