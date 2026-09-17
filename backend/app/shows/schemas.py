"""Public schema boundary for the Shows domain.

Schemas are re-exported from the shared schema module during the incremental V2
migration so import/export compatibility stays unchanged while callers can depend
on the feature boundary now.
"""

from app.schemas import MAX_EPISODES, ResourceId, ShowPatch, ShowPayload, ShowView

__all__ = ["MAX_EPISODES", "ResourceId", "ShowPatch", "ShowPayload", "ShowView"]
