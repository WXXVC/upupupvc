from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .db import get_connection


@dataclass
class DownloadTask:
    id: int
    batch_id: Optional[int]
    url: str
    download_format: Optional[str]
    file_type: str
    status: str
    progress: float
    speed: float
    downloaded: int
    total_size: int
    error: Optional[str]
    save_path: Optional[str]
    filename: Optional[str]
    retries: int
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class DownloadBatch:
    id: int
    title: Optional[str]
    description: Optional[str]
    status: str
    auto_upload: Optional[int]
    transcode_video_codec: Optional[str]
    transcode_video_format: Optional[str]
    transcode_image_format: Optional[str]
    upload_postprocess: Optional[str]
    upload_postprocess_path: Optional[str]
    total_count: int
    completed_count: int
    failed_count: int
    progress: float
    error: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class DownloadListItem:
    id: int
    kind: str
    title: str
    url: Optional[str]
    download_format: Optional[str]
    file_type: str
    status: str
    progress: float
    speed: float
    downloaded: int
    total_size: int
    error: Optional[str]
    save_path: Optional[str]
    filename: Optional[str]
    retries: int
    child_count: int
    completed_count: int
    failed_count: int
    description: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


def _normalize_file_type(raw_type: Optional[str], save_path: Optional[str], filename: Optional[str], url: Optional[str]) -> str:
    probe = save_path or filename or url or ''
    suffix = Path(str(probe)).suffix.lower()
    if suffix in {'.mp4', '.mkv', '.mov', '.webm', '.m4v', '.avi', '.ts'}:
        return 'video'
    if suffix in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}:
        return 'image'
    if suffix in {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus'}:
        return 'audio'
    if raw_type in {'video', 'image', 'audio', 'file'}:
        return raw_type
    return 'file'


def _row_to_task(row) -> DownloadTask:
    return DownloadTask(
        id=row['id'],
        batch_id=row['batch_id'],
        url=row['url'],
        download_format=row['download_format'],
        file_type=_normalize_file_type(row['file_type'], row['save_path'], row['filename'], row['url']),
        status=row['status'],
        progress=row['progress'],
        speed=row['speed'],
        downloaded=row['downloaded'],
        total_size=row['total_size'],
        error=row['error'],
        save_path=row['save_path'],
        filename=row['filename'],
        retries=row['retries'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def create_batch(
    title: str,
    description: Optional[str],
    total_count: int,
    *,
    auto_upload: Optional[bool] = None,
    transcode_video_codec: Optional[str] = None,
    transcode_video_format: Optional[str] = None,
    transcode_image_format: Optional[str] = None,
    upload_postprocess: Optional[str] = None,
    upload_postprocess_path: Optional[str] = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO download_batches (
                title, description, status, auto_upload,
                transcode_video_codec, transcode_video_format, transcode_image_format,
                upload_postprocess, upload_postprocess_path, total_count
            )
            VALUES (
                :title, :description, 'pending', :auto_upload,
                :transcode_video_codec, :transcode_video_format, :transcode_image_format,
                :upload_postprocess, :upload_postprocess_path, :total_count
            )
            """,
            {
                'title': title,
                'description': description,
                'auto_upload': None if auto_upload is None else (1 if auto_upload else 0),
                'transcode_video_codec': transcode_video_codec,
                'transcode_video_format': transcode_video_format,
                'transcode_image_format': transcode_image_format,
                'upload_postprocess': upload_postprocess,
                'upload_postprocess_path': upload_postprocess_path,
                'total_count': total_count,
            },
        )
        conn.commit()
        return cur.lastrowid


def get_batch(batch_id: int) -> Optional[DownloadBatch]:
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM download_batches WHERE id = :id', {'id': batch_id}).fetchone()
    if not row:
        return None
    return DownloadBatch(**dict(row))


def update_batch(batch_id: int, **fields) -> None:
    if not fields:
        return
    fields['id'] = batch_id
    assignments = ', '.join([f"{k} = :{k}" for k in fields if k != 'id'])
    with get_connection() as conn:
        conn.execute(
            f'UPDATE download_batches SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id',
            fields,
        )
        conn.commit()


def create_tasks(urls: Iterable[dict] | Iterable[str], batch_id: Optional[int] = None) -> List[int]:
    ids: List[int] = []
    with get_connection() as conn:
        for item in urls:
            if isinstance(item, dict):
                url = item.get('url')
                filename = item.get('filename')
                download_format = item.get('format')
            else:
                url = item
                filename = None
                download_format = None
            cur = conn.execute(
                """
                INSERT INTO download_tasks (batch_id, url, download_format, file_type, status, filename)
                VALUES (:batch_id, :url, :download_format, 'unknown', 'pending', :filename)
                """,
                {'batch_id': batch_id, 'url': url, 'download_format': download_format, 'filename': filename},
            )
            ids.append(cur.lastrowid)
        conn.commit()
    return ids


def list_tasks(status: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[DownloadTask]:
    where = []
    params = {}
    if status:
        where.append('status = :status')
        params['status'] = status
    if search:
        where.append('(url LIKE :q OR filename LIKE :q)')
        params['q'] = f'%{search}%'
    clause = ' WHERE ' + ' AND '.join(where) if where else ''
    with get_connection() as conn:
        rows = conn.execute(
            f'SELECT * FROM download_tasks{clause} ORDER BY id DESC LIMIT :limit OFFSET :offset',
            {**params, 'limit': limit, 'offset': offset},
        ).fetchall()
    return [_row_to_task(row) for row in rows]


def list_task_groups(
    status: Optional[str] = None,
    search: Optional[str] = None,
    file_type: Optional[str] = None,
    completed_from: Optional[str] = None,
    completed_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[DownloadListItem]:
    with get_connection() as conn:
        task_rows = conn.execute('SELECT * FROM download_tasks ORDER BY id DESC').fetchall()
        batch_rows = conn.execute('SELECT * FROM download_batches ORDER BY id DESC').fetchall()
    tasks = [_row_to_task(row) for row in task_rows]
    grouped: dict[int, list[DownloadTask]] = {}
    items: list[DownloadListItem] = []
    for task in tasks:
        if task.batch_id:
            grouped.setdefault(task.batch_id, []).append(task)
            continue
        items.append(
            DownloadListItem(
                id=task.id,
                kind='task',
                title=task.filename or task.url or f'任务 #{task.id}',
                url=task.url,
                download_format=task.download_format,
                file_type=task.file_type,
                status=task.status,
                progress=task.progress,
                speed=task.speed,
                downloaded=task.downloaded,
                total_size=task.total_size,
                error=task.error,
                save_path=task.save_path,
                filename=task.filename,
                retries=task.retries,
                child_count=1,
                completed_count=1 if task.status == 'completed' else 0,
                failed_count=1 if task.status == 'failed' else 0,
                description=None,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
        )
    for row in batch_rows:
        batch = DownloadBatch(**dict(row))
        children = grouped.get(batch.id, [])
        if not children:
            continue
        sample = children[0]
        batch_type = sample.file_type if len({child.file_type for child in children}) == 1 else 'file'
        items.append(
            DownloadListItem(
                id=batch.id,
                kind='batch',
                title=batch.title or f'批量下载 #{batch.id}',
                url=None,
                download_format=None,
                file_type=batch_type,
                status=batch.status,
                progress=batch.progress,
                speed=sum(child.speed for child in children),
                downloaded=sum(child.downloaded for child in children),
                total_size=sum(child.total_size for child in children),
                error=batch.error,
                save_path=None,
                filename=None,
                retries=0,
                child_count=len(children),
                completed_count=batch.completed_count,
                failed_count=batch.failed_count,
                description=batch.description,
                created_at=batch.created_at,
                updated_at=batch.updated_at,
            )
        )
    if search:
        q = search.lower()
        items = [item for item in items if q in (item.title or '').lower() or q in (item.url or '').lower() or q in (item.description or '').lower()]
    if status:
        items = [item for item in items if item.status == status]
    if file_type:
        items = [item for item in items if item.file_type == file_type]
    if completed_from or completed_to:
        items = [
            item for item in items
            if item.status == 'completed'
            and (not completed_from or (item.updated_at or '') >= f'{completed_from} 00:00:00')
            and (not completed_to or (item.updated_at or '') <= f'{completed_to} 23:59:59')
        ]
    items.sort(key=lambda item: (item.updated_at or '', item.id), reverse=True)
    return items[offset:offset + limit]


def list_batch_children(batch_id: int) -> List[DownloadTask]:
    with get_connection() as conn:
        rows = conn.execute('SELECT * FROM download_tasks WHERE batch_id = :batch_id ORDER BY id ASC', {'batch_id': batch_id}).fetchall()
    return [_row_to_task(row) for row in rows]


def get_task(task_id: int) -> Optional[DownloadTask]:
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM download_tasks WHERE id = :id', {'id': task_id}).fetchone()
    if not row:
        return None
    return _row_to_task(row)


def update_task(task_id: int, **fields) -> None:
    if not fields:
        return
    fields['id'] = task_id
    assignments = ', '.join([f"{k} = :{k}" for k in fields if k != 'id'])
    with get_connection() as conn:
        conn.execute(
            f'UPDATE download_tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id',
            fields,
        )
        conn.commit()
    task = get_task(task_id)
    if task and task.batch_id:
        refresh_batch(task.batch_id)


def refresh_batch(batch_id: int) -> None:
    children = list_batch_children(batch_id)
    if not children:
        update_batch(batch_id, status='completed', progress=100, completed_count=0, failed_count=0, total_count=0)
        return
    total = len(children)
    completed = sum(1 for child in children if child.status == 'completed')
    failed = sum(1 for child in children if child.status == 'failed')
    canceled = sum(1 for child in children if child.status == 'canceled')
    running = any(child.status in {'downloading', 'queued'} for child in children)
    paused = any(child.status == 'paused' for child in children)
    progress = sum(child.progress for child in children) / max(total, 1)
    error = next((child.error for child in children if child.error), None)
    if completed == total:
        status = 'completed'
    elif failed == total:
        status = 'failed'
    elif canceled == total:
        status = 'canceled'
    elif running:
        status = 'downloading'
    elif paused:
        status = 'paused'
    else:
        status = 'pending'
    update_batch(batch_id, status=status, progress=progress, completed_count=completed, failed_count=failed, error=error, total_count=total)


def delete_task(task_id: int) -> None:
    task = get_task(task_id)
    with get_connection() as conn:
        conn.execute('DELETE FROM download_tasks WHERE id = :id', {'id': task_id})
        conn.commit()
    if task and task.batch_id:
        refresh_batch(task.batch_id)


def delete_batch(batch_id: int) -> None:
    with get_connection() as conn:
        conn.execute('DELETE FROM download_tasks WHERE batch_id = :id', {'id': batch_id})
        conn.execute('DELETE FROM download_batches WHERE id = :id', {'id': batch_id})
        conn.commit()
