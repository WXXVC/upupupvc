# Telegram 媒体下载与上传系统 (M1)

## 本地运行

```bash
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9988
```

访问 `http://localhost:9988`，首次进入将跳转到配置页。

## M2 认证占位说明

当前内置 TDLib Stub 用于打通认证流程与事件推送：
- 配置完成后会触发认证状态 `wait_code`
- 提交验证码时输入 `2fa` 将触发 `wait_password`（模拟两步验证）
- 提交任意非空密码后进入 `ready`

## M3 下载器说明

- 已支持直链文件/图片/音视频的基础流式下载与断点续传
- 当服务器支持 `Accept-Ranges` 且文件较大时自动启用多连接分块下载
- 已支持基础 `m3u8` 解析与分片并发下载（ts 分片拼接，输出为 `.ts`）

## M4 上传器说明

- 已实现上传任务模型与队列调度（TDLib 不可用时自动降级为 Stub）
- 下载完成后自动加入上传队列
- 大文件按阈值进行本地分片（优先 `ffmpeg -c copy`，不可用则 Python 分片）
- 上传任务支持取消/重试
- 上传成功后按策略执行删除（`upload_postprocess=delete`）

## TDLib 集成说明

- 需要提供 `tdjson` 动态库路径（Windows: `tdjson.dll`）
- 认证流程依赖 TDLib `authorizationState` 状态机
- 上传进度基于 `updateFile` 回调的 `remote.uploaded_size` 与 `is_uploading_*` 字段
 
## FFmpeg 依赖

- 项目通过 Python 依赖 `imageio-ffmpeg` 自动提供 ffmpeg 二进制（含分片与 m3u8）
- 若无需 m3u8/转封装，可不额外配置系统 ffmpeg

## M5 前端

- 顶部全局状态展示（磁盘空间/认证状态）
- 任务状态徽章与进度条
- 主题切换（浅色/深色）
- 日志页面与任务详情面板
- 任务列表分页与主题持久化

## Docker

```bash
docker build -t tg-media .
docker run -p 9988:9988 \
  -v $PWD/data.db:/app/data.db \
  -v $PWD/downloads:/app/downloads \
  tg-media
```

### 任务持久化说明

- 下载/上传任务记录保存在 `data.db`（SQLite），需挂载持久化卷：`-v $PWD/data.db:/app/data.db`
- 建议同时挂载下载目录，避免容器重启后文件丢失：`-v $PWD/downloads:/app/downloads`
- 下载路径需在配置页设置为容器内路径（如 `/app/downloads`）
