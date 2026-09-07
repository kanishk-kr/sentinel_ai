import pytest
from unittest.mock import AsyncMock
from src.policy_gateway.gateway import policy_gateway
from src.shared.models import User, UserRole

@pytest.mark.asyncio
async def test_policy_gateway_authorizes_admin():
    db_mock = AsyncMock()
    user = User(
        username="admin",
        email="admin@test.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    
    decision = await policy_gateway.authorize(
        action="some_action",
        user=user,
        context=None,
        db=db_mock
    )
    
    assert decision.allowed is True
    assert decision.risk_tier == "LOW"

@pytest.mark.asyncio
async def test_policy_gateway_restricts_viewer():
    db_mock = AsyncMock()
    user = User(
        username="viewer",
        email="viewer@test.local",
        password_hash="hash",
        role=UserRole.VIEWER,
    )
    
    decision = await policy_gateway.authorize(
        action="code_exec",
        user=user,
        context=None,
        db=db_mock
    )
    
    assert decision.allowed is False
    assert decision.requires_approval is False
