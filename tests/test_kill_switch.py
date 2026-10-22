"""
Unit tests for kill switch functionality
"""

import pytest
from mailagent.core.types import DraftStatus
from mailagent.core.database import Database


class MockDatabase:
    """Mock database for testing"""

    def __init__(self):
        self.drafts = {}  # {draft_id: Draft}
        self.kill_switch_active = False
        self.draft_counter = 0

    async def save_draft(self, draft):
        draft_id = f"draft_{self.draft_counter}"
        self.draft_counter += 1
        self.drafts[draft_id] = draft
        return draft_id

    async def get_draft(self, draft_id):
        if draft_id in self.drafts:
            return {"id": draft_id, "status": self.drafts[draft_id].status.value}
        return None

    async def update_draft_status(self, draft_id, status):
        if draft_id in self.drafts:
            self.drafts[draft_id].status = status
            return True
        return False

    async def is_kill_switch_active(self):
        return self.kill_switch_active

    async def activate_kill_switch(self, reason, activated_by):
        self.kill_switch_active = True
        # Cancel all pending drafts
        cancelled_count = 0
        for draft_id, draft in self.drafts.items():
            if draft.status == DraftStatus.PENDING:
                draft.status = DraftStatus.CANCELLED
                cancelled_count += 1
        return True


@pytest.mark.asyncio
async def test_kill_switch_cancels_pending_drafts():
    """Test that activating kill switch cancels all pending drafts"""
    db = MockDatabase()
    from mailagent.core.types import Draft

    # Create some pending drafts
    draft1 = Draft(email_id="email_1", classification_id="class_1", content="Draft 1")
    draft2 = Draft(email_id="email_2", classification_id="class_2", content="Draft 2")
    draft3 = Draft(email_id="email_3", classification_id="class_3", content="Draft 3")

    draft1_id = await db.save_draft(draft1)
    draft2_id = await db.save_draft(draft2)
    draft3_id = await db.save_draft(draft3)

    # Set one draft to already sent
    db.drafts[draft1_id].status = DraftStatus.SENT

    # Activate kill switch
    result = await db.activate_kill_switch("Test activation", "test_user")

    assert result is True
    assert db.kill_switch_active is True

    # Check that pending drafts were cancelled
    assert db.drafts[draft2_id].status == DraftStatus.CANCELLED
    assert db.drafts[draft3_id].status == DraftStatus.CANCELLED

    # Check that sent draft was not cancelled
    assert db.drafts[draft1_id].status == DraftStatus.SENT


@pytest.mark.asyncio
async def test_kill_switch_state_persistence():
    """Test that kill switch state is persistent"""
    db = MockDatabase()

    # Initially inactive
    assert await db.is_kill_switch_active() is False

    # Activate
    await db.activate_kill_switch("Test", "test_user")

    # Should be active
    assert await db.is_kill_switch_active() is True
