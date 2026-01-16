from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patch_gethostname():
    with patch('socket.gethostname', return_value='testhost1'):
        yield
