from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .db import get_connection


@dataclass
class UploadTask:
    id: int
    batch_id: Optional[int]
    source_path: str
    target_channel: Optional[str]
    status: str
    progress: float
    speed: float
    uploaded: int
    total_size: int
    error: Optional[str]
    description: Optional[str]
    postprocess: Optional[str]
    postprocess_path: Optional[str]
    file_id: Optional[int]
    part_index: Optional[int]
    part_total: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class UploadBatch:
    id: int
    title: Optional[str]
    description: Optional[str]
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    progress: float
    error: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class UploadListItem:
    id: int
    kind: str
    title: str
    source_path: Optional[str]
    target_channel: Optional[str]
    status: str
    progress: float
    speed: float
    uploaded: int
    total_size: int
    error: Optional[str]
    description: Optional[str]
    file_id: Optional[int]
    part_index: Optional[int]
    part_total: Optional[int]
    child_count: int
    completed_count: int
    failed_count: int
    created_at: Optional[str]
    updated_at: Optional[str]


def _row_to_task(row) -> UploadTask:
    return UploadTask(
        id=row['id'],
        batch_id=row['batch_id'],
        source_path=row['source_path'],
        target_channel=row['target_channel'],
        status=row['status'],
        progress=row['progress'],
        speed=row['speed'],
        uploaded=row['uploaded'],
        total_size=row['total_size'],
        error=row['error'],
        description=row['description'],
        postprocess=row['postprocess'],
        postprocess_path=row['postprocess_path'],
        file_id=row['file_id'],
        part_index=row['part_index'],
        part_total=row['part_total'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def create_batch(title: str, description: Optional[str], total_count: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO upload_batches (title, description, status, total_count)
            VALUES (:title, :description, 'pending', :total_count)
            """,
            {'title': title, 'description': description, 'total_count': total_count},
        )
        conn.commit()
        return cur.lastrowid


def get_batch(batch_id: int) -> Optional[UploadBatch]:
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM upload_batches WHERE id = :id', {'id': batch_id}).fetchone()
    if not row:
        return None
    return UploadBatch(**dict(row))


def update_batch(batch_id: int, **fields) -> None:
    if not fields:
        return
    fields['id'] = batch_id
    assignments = ', '.join([f"{k} = :{k}" for k in fields if k != 'id'])
    with get_connection() as conn:
        conn.execute(
            f'UPDATE upload_batches SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id',
            fields,
        )
        conn.commit()


def create_task(
    source_path: str,
    target_channel: Optional[str],
    description: Optional[str] = None,
    part_index: Optional[int] = None,
    part_total: Optional[int] = None,
    batch_id: Optional[int] = None,
    postprocess: Optional[str] = None,
    postprocess_path: Optional[str] = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO upload_tasks (
                batch_id, source_path, target_channel, status, description,
                postprocess, postprocess_path, part_index, part_total
            )
            VALUES (
                :batch_id, :source_path, :target_channel, 'pending', :description,
                :postprocess, :postprocess_path, :part_index, :part_total
            )
            """,
            {
                'batch_id': batch_id,
                'source_path': source_path,
                'target_channel': target_channel,
                'description': description,
                'postprocess': postprocess,
                'postprocess_path': postprocess_path,
                'part_index': part_index,
                'part_total': part_total,
            },
        )
        conn.commit()
        return cur.lastrowid


def list_tasks(status: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[UploadTask]:
    where = []
    params = {}
    if status:
        where.append('status = :status')
        params['status'] = status
    if search:
        where.append('(source_path LIKE :q OR description LIKE :q)')
        params['q'] = f'%{search}%'
    clause = ' WHERE ' + ' AND '.join(where) if where else ''
    with get_connection() as conn:
        rows = conn.execute(
            f'SELECT * FROM upload_tasks{clause} ORDER BY id DESC LIMIT :limit OFFSET :offset',
            {**params, 'limit': limit, 'offset': offset},
        ).fetchall()
    return [_row_to_task(row) for row in rows]


def list_task_groups(status: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[UploadListItem]:
    with get_connection() as conn:
        task_rows = conn.execute('SELECT * FROM upload_tasks ORDER BY id DESC').fetchall()
        batch_rows = conn.execute('SELECT * FROM upload_batches ORDER BY id DESC').fetchall()

    tasks = [_row_to_task(row) for row in task_rows]
    items: list[UploadListItem] = []
    grouped: dict[int, list[UploadTask]] = {}
    for task in tasks:
        if task.batch_id:
            grouped.setdefault(task.batch_id, []).append(task)
            continue
        title = Path(task.source_path).name or task.source_path or f'任务 #{task.id}'
        items.append(
            UploadListItem(
                id=task.id,
                kind='task',
                title=title,
                source_path=task.source_path,
                target_channel=task.target_channel,
                status=task.status,
                progress=task.progress,
                speed=task.speed,
                uploaded=task.uploaded,
                total_size=task.total_size,
                error=task.error,
                description=task.description,
                file_id=task.file_id,
                part_index=task.part_index,
                part_total=task.part_total,
                child_count=1,
                completed_count=1 if task.status == 'completed' else 0,
                failed_count=1 if task.status == 'failed' else 0,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
        )

    for row in batch_rows:
        batch = UploadBatch(**dict(row))
        children = grouped.get(batch.id, [])
        if not children:
            continue
        items.append(
            UploadListItem(
                id=batch.id,
                kind='batch',
                title=batch.title or f'批量上传 #{batch.id}',
                source_path=None,
                target_channel=children[0].target_channel if children else None,
                status=batch.status,
                progress=batch.progress,
                speed=0,
                uploaded=sum(child.uploaded for child in children),
                total_size=sum(child.total_size for child in children),
                error=batch.error,
                description=batch.description,
                file_id=None,
                part_index=None,
                part_total=None,
                child_count=len(children),
                completed_count=batch.completed_count,
                failed_count=batch.failed_count,
                created_at=batch.created_at,
                updated_at=batch.updated_at,
            )
        )

    if search:
        q = search.lower()
        items = [item for item in items if q in (item.title or '').lower() or q in (item.description or '').lower() or q in (item.source_path or '').lower()]
    if status:
        items = [item for item in items if item.status == status]
    items.sort(key=lambda item: (item.updated_at or '', item.id), reverse=True)
    return items[offset:offset + limit]


def list_batch_children(batch_id: int) -> List[UploadTask]:
    with get_connection() as conn:
        rows = conn.execute('SELECT * FROM upload_tasks WHERE batch_id = :batch_id ORDER BY id ASC', {'batch_id': batch_id}).fetchall()
    return [_row_to_task(row) for row in rows]


def get_task(task_id: int) -> Optional[UploadTask]:
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM upload_tasks WHERE id = :id', {'id': task_id}).fetchone()
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
            f'UPDATE upload_tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id',
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
    uploading = any(child.status == 'uploading' for child in children)
    queued = any(child.status in {'queued', 'pending', 'auth_required'} for child in children)
    progress = sum(child.progress for child in children) / max(total, 1)
    error = next((child.error for child in children if child.error), None)
    if completed == total:
        status = 'completed'
    elif failed == total:
        status = 'failed'
    elif canceled == total:
        status = 'canceled'
    elif uploading:
        status = 'uploading'
    elif queued:
        status = 'queued'
    else:
        status = 'pending'
    update_batch(batch_id, status=status, progress=progress, completed_count=completed, failed_count=failed, error=error, total_count=total)


def delete_task(task_id: int) -> None:
    task = get_task(task_id)
    with get_connection() as conn:
        conn.execute('DELETE FROM upload_tasks WHERE id = :id', {'id': task_id})
        conn.commit()
    if task and task.batch_id:
        refresh_batch(task.batch_id)


def delete_batch(batch_id: int) -> None:
    with get_connection() as conn:
        conn.execute('DELETE FROM upload_tasks WHERE batch_id = :id', {'id': batch_id})
        conn.execute('DELETE FROM upload_batches WHERE id = :id', {'id': batch_id})
        conn.commit()
