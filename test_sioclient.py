from unittest.mock import AsyncMock

import pytest
import socketio
import sioclient


@pytest.mark.asyncio
async def test_client():
    sio = AsyncMock(spec=sioclient.sio)
    sioclient.sio = sio

    #Test main into connect
    await sioclient.main(8080)
    sio.connect.assert_awaited_with('http://localhost:8080', namespaces=['/client', '/'])

    #Test connect into register-client
    await sioclient.connect()
    sio.emit.assert_awaited_with('register-client', namespace='/client')
