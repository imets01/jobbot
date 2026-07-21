from analyzer import CANDIDATE_PROFILE
from backend.repository import get_or_create_profile, reset_profile, update_profile


def test_candidate_profile_persists_and_versions(session_factory):
    with session_factory() as session:
        initial = get_or_create_profile(session)
        assert initial.content == CANDIDATE_PROFILE.strip()
        assert initial.version == 1
        updated = update_profile(session, "Technical security engineer seeking junior roles." * 2)
        assert updated.version == 2
        session.commit()

    with session_factory() as session:
        persisted = get_or_create_profile(session)
        assert "Technical security engineer" in persisted.content
        assert persisted.version == 2
        restored = reset_profile(session)
        assert restored.content == CANDIDATE_PROFILE.strip()
        assert restored.version == 3
