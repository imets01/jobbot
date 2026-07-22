from backend.profile_service import DEFAULT_PROFILE
from backend.repository import (
    get_or_create_profile,
    get_structured_profile,
    reset_structured_profile,
    update_structured_profile,
)


def test_candidate_profile_persists_and_versions(session_factory):
    with session_factory() as session:
        initial = get_or_create_profile(session)
        structured = get_structured_profile(session)
        assert structured["skills"] == DEFAULT_PROFILE["skills"]
        assert initial.version == 1
        structured["full_name"] = "Ada Candidate"
        structured["skills"] = [*structured["skills"], "Terraform"]
        updated = update_structured_profile(session, structured)
        assert updated.version == 2
        session.commit()

    with session_factory() as session:
        persisted = get_or_create_profile(session)
        structured = get_structured_profile(session)
        assert structured["full_name"] == "Ada Candidate"
        assert "Terraform" in structured["skills"]
        assert persisted.version == 2
        restored = reset_structured_profile(session)
        assert get_structured_profile(session)["full_name"] == ""
        assert restored.version == 3
