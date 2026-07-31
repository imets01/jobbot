import {
  ArrowRight,
  Check,
  FileText,
  MapPin,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { CheckChoice, TagInput } from "../components/FormControls";
import { useToast } from "../components/ToastProvider";
import { ErrorState, LoadingState, PageHeader } from "../components/Ui";
import type {
  CandidateProfile,
  SearchControls,
  SearchSourceCapability,
  StructuredCandidateProfile,
} from "../types";

const WORK_MODELS = ["Remote", "Hybrid", "Onsite"];
const STEPS = [
  { number: 1, label: "Candidate", description: "Set up once" },
  { number: 2, label: "Search", description: "Adjust and launch" },
];

function editableControls(value: SearchControls): SearchControls {
  const { updated_at: _updatedAt, ...editable } = value;
  return editable;
}

function controlsKey(value: SearchControls) {
  return JSON.stringify(editableControls(value));
}

function fileSize(bytes: number) {
  return bytes >= 1_048_576
    ? `${(bytes / 1_048_576).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function candidateProfileReady(profile: StructuredCandidateProfile) {
  return Boolean(
    profile.full_name.trim()
    && profile.professional_summary.trim()
    && profile.skills.length,
  );
}

export function SearchPage() {
  const [step, setStep] = useState(1);
  const [setupComplete, setSetupComplete] = useState(false);
  const [record, setRecord] = useState<CandidateProfile | null>(null);
  const [savedProfile, setSavedProfile] = useState<StructuredCandidateProfile | null>(null);
  const [profile, setProfile] = useState<StructuredCandidateProfile | null>(null);
  const [savedControls, setSavedControls] = useState<SearchControls | null>(null);
  const [controls, setControls] = useState<SearchControls | null>(null);
  const [sources, setSources] = useState<SearchSourceCapability[]>([]);
  const [activeSearch, setActiveSearch] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { showToast } = useToast();

  const load = async () => {
    setError("");
    try {
      const [candidate, searchControls, capabilities, active] = await Promise.all([
        api.profile(),
        api.searchControls(),
        api.searchSources(),
        api.activeRun(),
      ]);
      setRecord(candidate);
      setSavedProfile(structuredClone(candidate.profile));
      setProfile(structuredClone(candidate.profile));
      setSavedControls(searchControls);
      setControls(searchControls);
      setSources(capabilities);
      setActiveSearch(Boolean(active));
      const candidateConfigured = candidateProfileReady(candidate.profile);
      setSetupComplete(candidateConfigured);
      setStep(candidateConfigured ? 2 : 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to prepare the job search");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const profileDirty = useMemo(
    () => Boolean(profile && savedProfile && JSON.stringify(profile) !== JSON.stringify(savedProfile)),
    [profile, savedProfile],
  );
  const controlsDirty = useMemo(
    () => Boolean(controls && savedControls && controlsKey(controls) !== controlsKey(savedControls)),
    [controls, savedControls],
  );

  useEffect(() => {
    const dirty = profileDirty || controlsDirty;
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const warnOnNavigation = (event: MouseEvent) => {
      if (!dirty) return;
      const link = (event.target as Element | null)?.closest("a[href]") as HTMLAnchorElement | null;
      if (link?.origin === window.location.origin && !window.confirm("Discard your unsaved search setup changes?")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", warnOnNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", warnOnNavigation, true);
    };
  }, [controlsDirty, profileDirty]);

  if (loading) return <LoadingState label="Preparing your job search" />;
  if (error || !record || !profile || !savedProfile || !controls || !savedControls) {
    return <ErrorState message={error || "Search setup unavailable"} onRetry={load} />;
  }

  const updateProfile = <K extends keyof StructuredCandidateProfile>(key: K, value: StructuredCandidateProfile[K]) => {
    setProfile((current) => current ? { ...current, [key]: value } : current);
  };
  const updateControls = <K extends keyof SearchControls>(key: K, value: SearchControls[K]) => {
    setControls((current) => current ? { ...current, [key]: value } : current);
  };

  const saveCandidate = async () => {
    if (!profileDirty) return record;
    const cleaned = {
      ...profile,
      languages: profile.languages.filter((entry) => entry.language.trim()),
    };
    const value = await api.saveProfile(cleaned);
    setRecord(value);
    setProfile(structuredClone(value.profile));
    setSavedProfile(structuredClone(value.profile));
    return value;
  };

  const saveControls = async () => {
    if (!controlsDirty) return controls;
    const value = await api.saveSearchControls(editableControls(controls));
    setControls(value);
    setSavedControls(value);
    return value;
  };

  const continueFromCandidate = async () => {
    setSaving(true);
    try {
      await saveCandidate();
      setSetupComplete(true);
      setStep(2);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to save candidate profile", "error");
    } finally {
      setSaving(false);
    }
  };

  const uploadCV = async (file: File) => {
    setUploading(true);
    try {
      const cv = await api.uploadCV(file);
      setRecord((current) => current ? { ...current, cv } : current);
      showToast("CV uploaded and stored locally", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to upload CV", "error");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const extractProfile = async () => {
    setExtracting(true);
    try {
      await api.extractProfileFromCV();
      const candidate = await api.profile();
      setRecord(candidate);
      setSavedProfile(structuredClone(candidate.profile));
      setProfile(structuredClone(candidate.profile));
      showToast("Candidate profile extracted from CV", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to extract the CV", "error");
    } finally {
      setExtracting(false);
    }
  };

  const startSearch = async () => {
    setStarting(true);
    try {
      await saveCandidate();
      const currentControls = await saveControls();
      await api.startSearch(editableControls(currentControls));
      showToast("Job search started", "success");
      navigate("/dashboard");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to start job search", "error");
    } finally {
      setStarting(false);
    }
  };

  const openFullProfile = async () => {
    setSaving(true);
    try {
      await saveCandidate();
      navigate("/profile");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to save candidate profile", "error");
    } finally {
      setSaving(false);
    }
  };

  const candidateReady = candidateProfileReady(profile);
  const sourceTargetsReady = (
    (!controls.sources.includes("Greenhouse") || controls.greenhouse_boards.length > 0)
    && (!controls.sources.includes("Lever") || controls.lever_sites.length > 0)
  );
  const searchReady = Boolean(
    controls.keywords.length
    && controls.target_locations.length
    && controls.sources.length
    && sourceTargetsReady,
  );

  return (
    <>
      <PageHeader
        eyebrow={step === 1 && !setupComplete ? "First search setup" : "New search"}
        title={step === 1
          ? setupComplete ? "Update your candidate details" : "Set up your candidate profile"
          : "Find your best matching roles"}
        description={step === 1 && !setupComplete
          ? "Add your candidate evidence once. You can review and update it whenever your experience changes."
          : step === 1
            ? "Keep the evidence used for matching current, then return to roles and filters."
            : "Review the saved candidate overview, adjust roles and filters, then start the search immediately."}
        actions={activeSearch ? <Link className="button button-secondary" to="/dashboard">View active search <ArrowRight size={16} /></Link> : undefined}
      />

      <nav className="search-stepper" aria-label="Job search setup progress">
        {STEPS.map((item) => (
          <button
            type="button"
            key={item.number}
            className={`${step === item.number ? "is-current" : ""} ${step > item.number ? "is-complete" : ""}`}
            onClick={() => item.number < step && setStep(item.number)}
            disabled={item.number > step}
            aria-current={step === item.number ? "step" : undefined}
          >
            <span>{step > item.number ? <Check size={16} /> : item.number}</span>
            <div><strong>{item.label}</strong><small>{item.description}</small></div>
          </button>
        ))}
      </nav>

      {step === 1 && (
        <section className="search-wizard-grid">
          <div className="search-wizard-main">
            <article className="panel wizard-section">
              <div className="section-heading"><div><p className="eyebrow">Step 1 of 2</p><h2>Candidate evidence</h2></div><UserRound size={20} /></div>
              <p className="section-description">Upload a CV for deeper reasoning, then verify the core profile fields reused by every future search.</p>

              <div className="wizard-cv-card">
                <div className="wizard-cv-icon"><FileText size={24} /></div>
                <div>
                  <strong>{record.cv?.file_name ?? "Upload your CV"}</strong>
                  <span>{record.cv ? `${fileSize(record.cv.size_bytes)} · Stored locally` : "PDF or DOCX, up to 10 MB"}</span>
                  <small>{record.cv?.extracted_at ? "Profile fields have been extracted" : record.cv ? "Ready to extract structured profile data" : "Recommended for better matching and cover letters"}</small>
                </div>
                <div className="button-row">
                  <input ref={fileInput} className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => event.target.files?.[0] && void uploadCV(event.target.files[0])} />
                  <button className="button button-secondary" disabled={uploading} onClick={() => fileInput.current?.click()}><Upload size={16} /> {uploading ? "Uploading…" : record.cv ? "Replace CV" : "Upload CV"}</button>
                  <button className="button button-primary" disabled={!record.cv || extracting} onClick={extractProfile}><Sparkles size={16} /> {extracting ? "Extracting…" : "Extract Profile"}</button>
                </div>
              </div>

              <div className="section-divider" />
              <div className="form-grid wizard-basic-grid">
                <label>Full name<input value={profile.full_name} onChange={(event) => updateProfile("full_name", event.target.value)} autoComplete="name" /></label>
                <label>Email<input type="email" value={profile.email} onChange={(event) => updateProfile("email", event.target.value)} autoComplete="email" /></label>
                <label>Current location<div className="input-with-icon"><MapPin size={16} /><input value={profile.current_location} onChange={(event) => updateProfile("current_location", event.target.value)} placeholder="Zurich, Switzerland" /></div></label>
                <label>Total experience (years)<input type="number" min={0} max={80} step={0.5} value={profile.years_total_experience} onChange={(event) => updateProfile("years_total_experience", Number(event.target.value))} /></label>
              </div>
              <label className="wizard-summary-field">Professional summary<textarea rows={5} value={profile.professional_summary} onChange={(event) => updateProfile("professional_summary", event.target.value)} placeholder="A concise, factual summary of your background and direction" /></label>
              <div className="profile-field-stack wizard-tags">
                <TagInput label="Skills" values={profile.skills} onChange={(values) => updateProfile("skills", values)} placeholder="Python, Azure, Kubernetes…" />
              </div>
              <div className="wizard-inline-link"><button className="text-link" disabled={saving} onClick={openFullProfile}>Edit education, experience, languages, and cover-letter details <ArrowRight size={14} /></button></div>
            </article>
          </div>

          <aside className="search-wizard-aside">
            <article className="panel readiness-card">
              <p className="eyebrow">Candidate readiness</p>
              <h3>{candidateReady ? "Ready to match" : "Complete the essentials"}</h3>
              <ul>
                <li className={record.cv ? "is-ready" : ""}><span>{record.cv ? <Check size={13} /> : "1"}</span> CV evidence <small>Recommended</small></li>
                <li className={profile.full_name.trim() ? "is-ready" : ""}><span>{profile.full_name.trim() ? <Check size={13} /> : "2"}</span> Basic identity</li>
                <li className={profile.professional_summary.trim() ? "is-ready" : ""}><span>{profile.professional_summary.trim() ? <Check size={13} /> : "3"}</span> Professional summary</li>
                <li className={profile.skills.length ? "is-ready" : ""}><span>{profile.skills.length ? <Check size={13} /> : "4"}</span> Skills</li>
              </ul>
            </article>
            <article className="panel privacy-card"><ShieldCheck size={20} /><div><strong>Private by design</strong><p>The CV file and raw extracted text stay on this machine.</p></div></article>
          </aside>
        </section>
      )}

      {step === 2 && (
        <section className="search-wizard-grid">
          <div className="search-wizard-main">
            <article className="panel wizard-section">
              <div className="section-heading"><div><p className="eyebrow">Roles and filters</p><h2>What should Jobbot search for?</h2></div><Search size={20} /></div>
              <p className="section-description">Adjust these settings for this search, then launch directly. Changes are saved for the next search.</p>
              <div className="profile-field-stack">
                <TagInput label="Job search keywords" values={controls.keywords} onChange={(values) => updateControls("keywords", values)} placeholder="Solution Engineer, Security Engineer…" />
                <TagInput label="Target locations" values={controls.target_locations} onChange={(values) => updateControls("target_locations", values)} placeholder="Zurich, Switzerland" />
                <div><span className="field-label">Work model</span><div className="inline-check-grid">{WORK_MODELS.map((model) => <CheckChoice key={model} label={model} checked={controls.work_models.includes(model)} onChange={(checked) => updateControls("work_models", checked ? [...controls.work_models, model] : controls.work_models.filter((value) => value !== model))} />)}</div></div>
              </div>

              <div className="section-divider" />
              <div className="form-grid controls-score-grid">
                <label>Minimum match score<div className="range-field"><input type="range" min={0} max={100} step={5} value={controls.minimum_match_score} onChange={(event) => updateControls("minimum_match_score", Number(event.target.value))} /><strong>{controls.minimum_match_score}</strong></div><small className="field-help">Lower-scoring jobs will not appear in results.</small></label>
                <label>Top matches to return<input type="number" min={1} max={100} value={controls.number_of_jobs} onChange={(event) => updateControls("number_of_jobs", Math.max(1, Math.min(100, Number(event.target.value))))} /></label>
                <label>Maximum required experience<input type="number" min={0} max={80} step={0.5} value={controls.max_required_experience_years ?? ""} onChange={(event) => updateControls("max_required_experience_years", event.target.value === "" ? null : Number(event.target.value))} /><small className="field-help">Leave empty for no limit.</small></label>
              </div>
              <div className="control-choice-stack wizard-exclusions">
                <CheckChoice label="Include stretch roles" description="Allow stronger but less certain opportunities." checked={controls.include_stretch_roles} onChange={(checked) => updateControls("include_stretch_roles", checked)} />
                <CheckChoice label="Exclude unavailable languages" description="Hide jobs requiring languages missing from your profile." checked={controls.exclude_unavailable_languages} onChange={(checked) => updateControls("exclude_unavailable_languages", checked)} />
                <CheckChoice label="Exclude jobs outside selected locations" description="Treat target locations as a hard requirement." checked={controls.exclude_outside_locations} onChange={(checked) => updateControls("exclude_outside_locations", checked)} />
              </div>

              <div className="section-divider" />
              <span className="field-label">Search sources</span>
              <div className="source-choice-grid">{sources.map((source) => <CheckChoice key={source.name} label={source.name} description={source.note} disabled={!source.available} checked={controls.sources.includes(source.name)} onChange={(checked) => updateControls("sources", checked ? [...controls.sources, source.name] : controls.sources.filter((value) => value !== source.name))} />)}</div>
              {(controls.sources.includes("Greenhouse") || controls.sources.includes("Lever")) && (
                <div className="source-target-config">
                  <div><p className="eyebrow">Target companies</p><h3>Company job boards</h3><p>Greenhouse and Lever expose public company feeds rather than a global search. Add each company board URL or site name to scan.</p></div>
                  {controls.sources.includes("Greenhouse") && (
                    <div>
                      <TagInput label="Greenhouse boards" values={controls.greenhouse_boards} onChange={(values) => updateControls("greenhouse_boards", values)} placeholder="Company | board token or URL" />
                      <small className="field-help">Example: Acme | acme, or https://boards.greenhouse.io/acme</small>
                    </div>
                  )}
                  {controls.sources.includes("Lever") && (
                    <div>
                      <TagInput label="Lever sites" values={controls.lever_sites} onChange={(values) => updateControls("lever_sites", values)} placeholder="Company | site name or URL" />
                      <small className="field-help">Example: Acme | acme, or https://jobs.lever.co/acme</small>
                    </div>
                  )}
                </div>
              )}
            </article>
          </div>

          <aside className="search-wizard-aside">
            <article className="panel review-summary-card candidate-overview-card">
              <div className="section-heading"><div><p className="eyebrow">Candidate overview</p><h3>{profile.full_name || "Candidate profile"}</h3></div><UserRound size={19} /></div>
              <p>{profile.professional_summary || "No professional summary provided."}</p>
              <div className="candidate-skill-preview" aria-label="Candidate skills">
                {profile.skills.slice(0, 5).map((skill) => <span className="badge badge-neutral" key={skill}>{skill}</span>)}
                {profile.skills.length > 5 && <span className="badge badge-neutral">+{profile.skills.length - 5} more</span>}
              </div>
              <dl className="wizard-summary-list">
                <div><dt>CV</dt><dd>{record.cv ? record.cv.file_name : "Not uploaded"}</dd></div>
                <div><dt>Location</dt><dd>{profile.current_location || "Not set"}</dd></div>
                <div><dt>Experience</dt><dd>{profile.years_total_experience} years</dd></div>
                <div><dt>Languages</dt><dd>{profile.languages.length || "—"}</dd></div>
              </dl>
              <div className="candidate-overview-actions">
                <button className="text-link" onClick={() => { setStep(1); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit core details <ArrowRight size={14} /></button>
                <Link className="text-link" to="/profile">Open full profile <ArrowRight size={14} /></Link>
              </div>
            </article>
            <article className="panel readiness-card">
              <p className="eyebrow">Search preview</p>
              <h3>{searchReady ? "Ready to search" : "Add the search scope"}</h3>
              <dl className="wizard-summary-list">
                <div><dt>Keywords</dt><dd>{controls.keywords.length || "—"}</dd></div>
                <div><dt>Locations</dt><dd>{controls.target_locations.length || "—"}</dd></div>
                <div><dt>Threshold</dt><dd>{controls.minimum_match_score}/100</dd></div>
                <div><dt>Results</dt><dd>Top {controls.number_of_jobs}</dd></div>
                <div><dt>Sources</dt><dd>{controls.sources.length || "—"}</dd></div>
                <div><dt>Company boards</dt><dd>{controls.greenhouse_boards.length + controls.lever_sites.length || "—"}</dd></div>
              </dl>
              {!sourceTargetsReady && <p className="inline-note">Add at least one company board for each selected ATS source.</p>}
            </article>
          </aside>
        </section>
      )}

      <footer className="wizard-footer">
        {step === 1 ? (
          <>
            <div className="wizard-footer-copy">
              <strong>{setupComplete ? "Update candidate details" : "One-time candidate setup"}</strong>
              <span>{setupComplete ? "Save any changes and return to this search." : "These details will be summarized instead of shown as a step next time."}</span>
            </div>
            <button className="button button-primary" disabled={saving || !candidateReady} onClick={continueFromCandidate}>{saving ? "Saving…" : setupComplete ? "Save & return to search" : "Save & continue"} <ArrowRight size={16} /></button>
          </>
        ) : (
          <>
            <div className="wizard-footer-copy">
              <strong>{activeSearch ? "A job search is already running" : controlsDirty ? "Updated filters ready" : "Search setup ready"}</strong>
              <span>{activeSearch ? "Open the results dashboard to follow its progress." : `Discover, score, and return up to ${controls.number_of_jobs} matches in one run.`}</span>
            </div>
            {activeSearch
              ? <Link className="button button-primary" to="/dashboard">View search progress <ArrowRight size={16} /></Link>
              : <button className="button button-primary button-large" disabled={starting || !candidateReady || !searchReady} onClick={startSearch}><Search size={18} /> {starting ? "Starting search…" : "Start Job Search"}</button>}
          </>
        )}
      </footer>
    </>
  );
}
