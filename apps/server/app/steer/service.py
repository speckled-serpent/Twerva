"""Record steer_actions and apply cluster is_active side effects (1.7c)."""

from __future__ import annotations

from app.models import Cluster, SteerAction
from app.models.enums import SteerActionType


DEACTIVATE_STEER_ACTIONS: frozenset[SteerActionType] = frozenset(
    {SteerActionType.KILL, SteerActionType.PAUSE},
)
DEFAULT_STEER_CREATED_BY: str = "human"


def apply_steer_action_to_cluster(
    cluster: Cluster,
    action: SteerActionType,
    reason: str | None = None,
    created_by: str | None = DEFAULT_STEER_CREATED_BY,
) -> SteerAction:
    """Insert an uncommitted SteerAction and mutate cluster `is_active`.

    Side effects (MVP):

    - `kill` / `pause`: `cluster.is_active = False`. Account rows are
      left unchanged (steer grain is the cluster).
    - `resume`: `cluster.is_active = True`.
    - `double_down`: log-only — the steer row is written, `is_active`
      is not changed. Cadence / generate boost waits for a later slice.

    Args:
        cluster: Cluster to record against (mutated for pause/kill/resume).
        action: Closed `SteerActionType`.
        reason: Optional freeform note.
        created_by: Freeform actor (`human`, agent name). Default `human`.

    Returns:
        Uncommitted SteerAction (caller adds + commits).
    """

    steer_action: SteerAction = SteerAction(
        cluster_id=cluster.id,
        action=action,
        reason=reason,
        created_by=created_by,
    )

    if action in DEACTIVATE_STEER_ACTIONS:
        cluster.is_active = False
    elif action == SteerActionType.RESUME:
        cluster.is_active = True

    return steer_action
