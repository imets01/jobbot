from datetime import date

from backend.repository import (
    delete_application,
    get_or_update_application,
    list_jobs,
    set_job_archived,
    upsert_job,
)


def test_application_status_notes_and_dates_update(session):
    job, _ = upsert_job(
        session,
        {
            "title": "Security Engineer",
            "company": "Example",
            "link": "https://linkedin.com/jobs/view/4412345678",
            "description": "Junior role.",
        },
    )
    application = get_or_update_application(
        session,
        job,
        status="Applied",
        application_date=date(2026, 7, 21),
        next_follow_up_date=date(2026, 7, 28),
        notes="Applied through the company portal.",
    )
    session.commit()

    assert application.status == "Applied"
    assert application.application_date == date(2026, 7, 21)
    assert application.next_follow_up_date == date(2026, 7, 28)
    assert application.notes == "Applied through the company portal."

    updated = get_or_update_application(
        session,
        job,
        status="Interviewing",
        application_date=application.application_date,
        next_follow_up_date=date(2026, 8, 1),
        notes="First interview scheduled.",
    )
    assert updated.id == application.id
    assert updated.status == "Interviewing"
    assert updated.notes == "First interview scheduled."
    assert job.archived is False

    archived = get_or_update_application(
        session,
        job,
        status="Archived",
        application_date=updated.application_date,
        next_follow_up_date=None,
        notes=updated.notes,
    )
    assert archived.status == "Archived"
    assert job.archived is True


def test_archive_action_creates_status_and_restores_it(session):
    job, _ = upsert_job(
        session,
        {
            "title": "Cloud Security Engineer",
            "company": "Example",
            "link": "https://linkedin.com/jobs/view/5512345678",
            "description": "Early-career security role.",
        },
    )
    session.commit()

    application = set_job_archived(session, job, True)
    session.commit()

    assert application is not None
    assert application.status == "Archived"
    assert job.archived is True

    archived_rows, archived_total = list_jobs(
        session,
        application_status="Archived",
        archived="archived",
    )
    assert archived_total == 1
    assert archived_rows[0][0].id == job.id
    assert archived_rows[0][2].status == "Archived"

    restored_application = set_job_archived(session, job, False)
    session.commit()

    assert restored_application is not None
    assert restored_application.status == "Saved"
    assert job.archived is False

    saved_rows, saved_total = list_jobs(
        session,
        application_status="Saved",
        archived="active",
    )
    assert saved_total == 1
    assert saved_rows[0][0].id == job.id


def test_application_can_be_untracked_without_deleting_job(session):
    job, _ = upsert_job(
        session,
        {
            "title": "Platform Engineer",
            "company": "Example",
            "link": "https://linkedin.com/jobs/view/6512345678",
            "description": "Platform engineering role.",
        },
    )
    application = get_or_update_application(
        session,
        job,
        status="Archived",
        application_date=None,
        next_follow_up_date=None,
        notes="No longer pursuing.",
    )
    session.commit()

    assert job.archived is True
    assert delete_application(session, job) is True
    session.commit()

    assert job.archived is False
    assert job.application is None
    assert session.get(type(job), job.id) is not None
    assert session.get(type(application), application.id) is None
    assert delete_application(session, job) is False
