"""Surveille les événements Vexa même si l'utilisateur ferme la page Nolya."""

import asyncio

from sqlmodel import Session, select

from app.db import engine
from app.models import RemoteMeeting, RemoteMeetingStatus
from app.remote_processing import finalize_remote_meeting, sync_remote_meeting

_loop: asyncio.AbstractEventLoop | None = None
_tasks: dict[str, asyncio.Task] = {}
_terminal = {
    RemoteMeetingStatus.COMPLETED,
    RemoteMeetingStatus.FAILED,
    RemoteMeetingStatus.STOPPED,
}


def bind_monitor_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def watch_remote_meeting(meeting_id: str) -> None:
    """Planifie un moniteur depuis une route sync ou async, sans en créer deux."""
    if not _loop or _loop.is_closed():
        return

    def create() -> None:
        if meeting_id not in _tasks or _tasks[meeting_id].done():
            _tasks[meeting_id] = _loop.create_task(_watch(meeting_id))

    _loop.call_soon_threadsafe(create)


def resume_remote_monitors() -> None:
    with Session(engine) as db:
        meetings = db.exec(select(RemoteMeeting)).all()
        for meeting in meetings:
            if meeting.status not in _terminal:
                watch_remote_meeting(meeting.id)


async def stop_remote_monitors() -> None:
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()


async def _watch(meeting_id: str) -> None:
    """Interroge Vexa régulièrement pour ne pas dépendre d'un événement WebSocket."""
    while True:
        with Session(engine) as db:
            meeting = db.get(RemoteMeeting, meeting_id)
            if not meeting or meeting.status in _terminal:
                return
        try:
            if await asyncio.to_thread(sync_remote_meeting, meeting_id):
                await asyncio.to_thread(finalize_remote_meeting, meeting_id)
                return
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(3)
