import pytest
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from src.security.audit_log import audit_service
from src.shared.models import AuditLog, AuditCheckpoint

@pytest.mark.asyncio
async def test_verify_chain_detects_tampering():
    db_mock = AsyncMock()
    
    # Create a valid chain
    prev_hash = "0" * 64
    payload1 = json.dumps({
        "seq": 1,
        "type": "test",
        "actor": "user1",
        "action": "action1",
        "resource": None,
        "model_or_tool": None,
        "input_hash": None,
        "output_hash": None,
        "risk_tier": None,
        "allowed": None,
        "timestamp": "",
    }, sort_keys=True)
    hash1 = hashlib.sha256(f"{prev_hash}||{payload1}".encode()).hexdigest()
    
    entry1 = AuditLog(
        sequence_number=1,
        entry_type="test",
        actor="user1",
        action="action1",
        prev_hash=prev_hash,
        entry_hash=hash1
    )
    
    payload2 = json.dumps({
        "seq": 2,
        "type": "test",
        "actor": "user1",
        "action": "action2",
        "resource": None,
        "model_or_tool": None,
        "input_hash": None,
        "output_hash": None,
        "risk_tier": None,
        "allowed": None,
        "timestamp": "",
    }, sort_keys=True)
    hash2 = hashlib.sha256(f"{hash1}||{payload2}".encode()).hexdigest()

    entry2 = AuditLog(
        sequence_number=2,
        entry_type="test",
        actor="user1",
        action="action2",
        prev_hash=hash1,
        entry_hash=hash2
    )

    result_mock_logs = MagicMock()
    result_mock_logs.scalars.return_value.all.return_value = [entry1, entry2]
    
    result_mock_cp = MagicMock()
    result_mock_cp.scalar_one_or_none.return_value = None

    db_mock.execute.side_effect = [result_mock_logs, result_mock_cp]

    result = await audit_service.verify_chain(db_mock)
    assert result["chain_integrity"] == "PASS"
    assert result["hash_mismatches"] == 0

    # Tamper with the first entry's action
    entry1.action = "tampered_action"
    
    result_mock_logs2 = MagicMock()
    result_mock_logs2.scalars.return_value.all.return_value = [entry1, entry2]
    db_mock.execute.side_effect = [result_mock_logs2, result_mock_cp]

    result_tampered = await audit_service.verify_chain(db_mock)
    assert result_tampered["chain_integrity"] == "FAIL"
    assert result_tampered["hash_mismatches"] > 0
