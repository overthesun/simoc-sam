import asyncio

from unittest.mock import patch

import pytest

from simoc_sam.db import init_db, close_db


@pytest.fixture(autouse=True)
def patch_gethostname():
    with patch('socket.gethostname', return_value='testhost1'):
        yield


@pytest.fixture
def db_conn(tmp_path):
    """Open a fresh isolated DB for each test and close it after."""
    conn = init_db(tmp_path / 'test.db')
    yield conn
    close_db()


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary log directory."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


async def wait_until(condition, timeout=5.0, interval=0.1):
    """Wait until condition() returns True or timeout occurs."""
    max_attempts = int(timeout / interval)
    for _ in range(max_attempts):
        if condition():
            return
        await asyncio.sleep(interval)
    pytest.fail(f"Condition not met within {timeout} seconds")


async def terminate_task(task):
    """Cancel a task and wait for it to finish."""
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
