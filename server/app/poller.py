"""Compatibilité : la synchronisation est désormais déclenchée par l'API."""

from app.remote_processing import finalize_remote_meeting, sync_remote_meeting

__all__ = ["finalize_remote_meeting", "sync_remote_meeting"]
