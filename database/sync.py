import logging

logger = logging.getLogger(__name__)

# Note: Cloud sync is no longer needed with the single DATABASE_URL approach.
# All data writes go directly to the target database (local or cloud).


def push_chapter_to_cloud(chapter_id: str):
    """
    Deprecated: Cloud sync is no longer needed with single DATABASE_URL.
    All writes go directly to the target database.
    """
    logger.warning("Cloud sync disabled - using single DATABASE_URL approach.")
    return


def push_series_bridge_cache(series_id: str):
    """
    Deprecated: Cloud sync is no longer needed with single DATABASE_URL.
    """
    logger.warning("Cloud sync disabled - using single DATABASE_URL approach.")
    return


def sync_all_to_cloud():
    """
    Deprecated: Cloud sync is no longer needed with single DATABASE_URL approach.
    All writes now go directly to the target database.
    """
    print("ℹ️  Cloud sync is disabled - using single DATABASE_URL approach instead.")
    return


if __name__ == "__main__":
    sync_all_to_cloud()
