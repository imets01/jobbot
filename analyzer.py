"""
analyzer.py
-----------
Loads scraped job JSON files from the `/data` directory and uses the Google
Gemini SDK (`google-genai`) to have the model parse each raw job description.

Gemini evaluates whether each job is a good fit for the candidate profile
(an entry-level technical security / solution engineer). It returns a *strict*
structured JSON object containing:

  - is_good_match (bool): True if the role fits the candidate's profile.
  - seniority_ok (bool): True if the role targets ~0-2 years of experience
                         (i.e. not a senior/lead role requiring many years).
  - verdict (str): A short human-readable explanation of the decision.

Structured output is enforced natively via the model's `response_schema` /
`response_mime_type` configuration, so responses are guaranteed valid JSON.

The API key is read from the environment via python-dotenv (see config.py).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

import config

# How many times to retry a request that hits a transient rate limit (429).
MAX_RETRIES = 3

# Candidate profile that Gemini uses as the yardstick for every job.
CANDIDATE_PROFILE = """\
Candidate profile:
- Informatics student at University of Zurich (UZH), finishing thesis in October.
- Early-career: roughly 1-2 years of combined internship experience, NOT senior.
- Experience: full-stack engineering intern, DevOps engineering intern at
  Swisscom, and currently a Security Solution Engineer intern at Microsoft.
- Technical skills: Python, Java, Go, Docker, Kubernetes, and Microsoft security
  solutions.
- Wants technical roles in security, solution/sales engineering (technical side),
  DevOps, or similar. Wants to KEEP the hands-on technical aspect.
- Does NOT want pure sales / account-management roles with little technical work.
- Prefers entry-level / junior roles targeting about 1-2 years of experience;
  avoid roles requiring 5+ years or Senior/Staff/Principal/Lead titles.
"""

# System instruction that constrains the model's role and behavior.
SYSTEM_INSTRUCTION = (
    "You are a precise job-matching assistant. Given a candidate profile and a "
    "raw job description, you decide whether the job is a realistic, relevant "
    "fit for the candidate. Be strict: reject pure-sales roles and roles that "
    "require far more experience than the candidate has."
)

# Structured response schema Gemini must adhere to.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_good_match": {
            "type": "boolean",
            "description": (
                "True if the role is a relevant technical fit for the candidate "
                "(security / solution / DevOps engineering, technical focus) AND "
                "is realistic for their early-career experience level."
            ),
        },
        "seniority_ok": {
            "type": "boolean",
            "description": (
                "True if the role targets roughly 0-2 years of experience and is "
                "not a Senior/Staff/Principal/Lead role requiring 5+ years."
            ),
        },
        "verdict": {
            "type": "string",
            "description": "Short one-sentence explanation, max 25 words.",
        },
    },
    "required": ["is_good_match", "seniority_ok", "verdict"],
}

# Instruction template describing the classification task.
USER_PROMPT_TEMPLATE = """\
{profile}

Using the candidate profile above, analyze the job delimited by triple backticks.

Decide:
  1. is_good_match: Is this a relevant, technical role (security, solution/sales
     engineering with a strong technical focus, DevOps, or similar) that suits
     the candidate? Reject roles that are mostly sales/account management with
     little hands-on technical work.
  2. seniority_ok: Does the role realistically target an early-career candidate
     (about 0-2 years)? Set false if it clearly requires 5+ years or is a
     Senior/Staff/Principal/Lead role.

Provide a short "verdict" (max 25 words) explaining your decision.

Job title: {title}
Company: {company}

Job description:
```
{description}
```
"""


def build_client() -> genai.Client:
    """Create a Gemini client, validating that the API key is present."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add "
            "your key."
        )
    return genai.Client(api_key=config.GEMINI_API_KEY)


# Backwards-compatible alias for existing callers.
_build_client = build_client


def _load_jobs(paths: list[Path]) -> list[tuple[Path, dict]]:
    """Load job JSON files from the supplied paths."""
    jobs: list[tuple[Path, dict]] = []
    for path in sorted(paths):
        try:
            with path.open("r", encoding="utf-8") as f:
                jobs.append((path, json.load(f)))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[analyzer] Skipping unreadable file {path.name}: {exc}")
    return jobs


def _parse_structured_response(raw_text: str) -> dict:
    """Parse the model's response into a dict, tolerating minor formatting.

    Falls back to extracting the first JSON object if extra text slips in.
    """
    text = raw_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def analyze_job(
    client: genai.Client,
    job: dict,
    candidate_profile: str = CANDIDATE_PROFILE,
) -> dict:
    """Send one job to Gemini and return the structured evaluation.

    Retries with exponential backoff on transient rate-limit (429) errors.
    """
    prompt = USER_PROMPT_TEMPLATE.format(
        profile=candidate_profile,
        title=job.get("title", "Unknown"),
        company=job.get("company", "Unknown"),
        description=job.get("description", "") or "(no description available)",
    )

    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    # Disable "thinking" so the whole token budget goes to the
                    # JSON answer. Without this, gemini-2.5 models spend tokens
                    # on internal reasoning and truncate the structured output.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    max_output_tokens=512,
                ),
            )
            break
        except genai_errors.ClientError as exc:
            # 429 = rate limit / quota. Back off and retry unless out of tries.
            if exc.code == 429 and attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(
                    f"[analyzer] Rate limited (429). Retrying in {wait}s "
                    f"(attempt {attempt}/{MAX_RETRIES - 1})..."
                )
                time.sleep(wait)
                continue
            raise

    # `response.text` is JSON constrained by the schema above.
    result = _parse_structured_response(response.text or "{}")

    # Normalize to guarantee the expected keys/types downstream.
    return {
        "is_good_match": bool(result.get("is_good_match", False)),
        "seniority_ok": bool(result.get("seniority_ok", False)),
        "verdict": str(result.get("verdict", "")).strip(),
    }


def analyze_all(
    data_dir: Path | None = None,
    job_paths: list[Path] | None = None,
    candidate_profile: str = CANDIDATE_PROFILE,
) -> list[dict]:
    """Analyze selected jobs, or every job in the data directory.

    Returns a list of result records combining basic job metadata with the
    structured Gemini evaluation. When ``job_paths`` is supplied, only those
    files are analyzed; this is used by the full scrape-and-analyze pipeline.
    """
    data_dir = data_dir or config.DATA_DIR
    if job_paths is None and not data_dir.exists():
        print(f"[analyzer] Data directory {data_dir} does not exist. Nothing to do.")
        return []

    client = _build_client()
    paths = job_paths if job_paths is not None else list(data_dir.glob("job_*.json"))
    jobs = _load_jobs(paths)
    print(f"[analyzer] Loaded {len(jobs)} job(s) for analysis.")

    results: list[dict] = []
    for index, (path, job) in enumerate(jobs):
        # Throttle requests to respect the free-tier requests-per-minute limit.
        # Skip the pause before the very first request.
        if index > 0 and config.ANALYZER_DELAY_SECONDS > 0:
            time.sleep(config.ANALYZER_DELAY_SECONDS)

        try:
            evaluation = analyze_job(
                client,
                job,
                candidate_profile=candidate_profile,
            )
        except Exception as exc:  # noqa: BLE001 - surface any API/parse error per job
            print(f"[analyzer] Failed to analyze {path.name}: {exc}")
            continue

        record = {
            "title": job.get("title"),
            "company": job.get("company"),
            "link": job.get("link"),
            "is_good_match": evaluation["is_good_match"],
            "seniority_ok": evaluation["seniority_ok"],
            "verdict": evaluation["verdict"],
        }
        results.append(record)

        flag = "MATCH" if record["is_good_match"] and record["seniority_ok"] else "skip"
        print(
            f"[analyzer] [{flag}] {record['title']} @ {record['company']} "
            f"-> {record['verdict']}"
        )

    return results


if __name__ == "__main__":
    analyze_all()
