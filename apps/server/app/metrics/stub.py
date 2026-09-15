"""Optional stub metric puller for mock-published jobs (1.7a-ii).

There is no real analytics vendor in Phase 1. After mock publish,
`POST /api/v1/post-jobs/{id}/metrics/stub` writes a deterministic
snapshot. Manual `POST .../metrics` is the operator path for any job.
"""

from app.models import PostJob


MOCK_PLATFORM_POST_ID_PREFIX: str = "mock-"
STUB_MOCK_VIEWS: int = 100
STUB_MOCK_LIKES: int = 10
STUB_MOCK_COMMENTS: int = 2
STUB_MOCK_SHARES: int = 1


def post_job_is_mock_published(post_job: PostJob) -> bool:
    """True when the job has a mock adapter `platform_post_id`.

    Args:
        post_job: Row whose platform id is inspected.

    Returns:
        True if `platform_post_id` starts with `mock-`.
    """

    platform_post_id: str | None = post_job.platform_post_id

    if platform_post_id is None:
        return False

    is_mock_published: bool = platform_post_id.startswith(MOCK_PLATFORM_POST_ID_PREFIX)

    return is_mock_published
