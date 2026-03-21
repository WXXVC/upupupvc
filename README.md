# 媒体下载与上传系统

单体全栈应用（FastAPI + SQLite），用于下载各类媒体文件并上传到 Telegram 频道。支持本地运行与 Docker 部署。

## 功能概览

- m3u8/HLS 与直链媒体下载（断点续传/分块）
- 集成 yt-dlp 增强通用站点下载与批量 URL 下载成功率
- 单链接下载支持先解析可用音视频格式（默认最高），批量下载默认最高
- 下载链路支持复用配置页代理（HTTP/SOCKS5）
- 下载任务管理与状态推送
- TDLib 认证与上传（支持回退 Stub）
- Telethon 连接支持可开关代理（HTTP/SOCKS5）
- 上传任务管理与后处理
- 日志页面与任务详情面板

## 技术栈

- 后端：FastAPI + Jinja2
- 数据库：SQLite（`data.db`）
- 任务调度：进程内异步 + 线程池
- 通信：SSE
- Telegram：MTProto（Telethon）

## 本地运行

```bash
python -m venv .venv
. .venv/bin/activate 
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9988
```
win端：一键启动 start.bat

访问 `http://localhost:9988`，首次进入将跳转到配置页。

## Docker 部署

```bash
docker run -d \
  --name upupupvc \
  -p 9988:9988 \
  -v $PWD/data.db:/app/data.db \
  -v $PWD/downloads:/app/downloads \
  ghcr.io/WXXVC/upupupvc:latest
```
ghcr.io/<你的 GitHub 用户名或组织名>/<仓库名>:latest


### 任务持久化说明

- 下载/上传任务记录保存在 `data.db`（SQLite），需挂载持久化卷：`-v $PWD/data.db:/app/data.db`
- 建议同时挂载下载目录，避免容器重启后文件丢失：`-v $PWD/downloads:/app/downloads`
- 下载路径需在配置页设置为容器内路径（如 `/app/downloads`）

## 配置与认证

- 需要配置 Telegram `api_id`、`api_hash`、手机号与目标频道
- 认证流程使用 MTProto（Telethon），首次上传会触发验证码/两步验证

## 下载与上传

- 已支持直链文件/图片/音视频的基础流式下载与断点续传
- 当服务器支持 `Accept-Ranges` 且文件较大时自动启用多连接分块下载
- m3u8/HLS：优先使用 ffmpeg 转封装（输出 `.mp4`），无 ffmpeg 时回退为 `.ts` 拼接
- 下载完成后可自动入队上传（可配置）
- 上传进度基于 `updateFile` 回调的 `remote.uploaded_size` 与 `is_uploading_*` 字段
- 上传后处理支持删除/移动（可配置路径模板）

## 前端与运维

- 顶部全局状态展示（磁盘空间/认证状态）
- 任务状态徽章与进度条
- 主题切换（浅色/深色，持久化）
- 日志页面与任务详情面板
- 任务列表分页

## 依赖说明

- `imageio-ffmpeg` 提供 ffmpeg 二进制，用于 m3u8 与视频分片
- `yt-dlp` 用于增强通用站点媒体下载能力，适合视频站点解析、格式枚举与更复杂的下载场景
- `telethon` 用于 MTProto 客户端上传
