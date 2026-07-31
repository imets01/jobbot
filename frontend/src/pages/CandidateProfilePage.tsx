import {
  FileText,
  RefreshCcw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { AddRowButton, CheckChoice, StringListField, TagInput } from "../components/FormControls";
import { useToast } from "../components/ToastProvider";
import { ErrorState, LoadingState, PageHeader } from "../components/Ui";
import type { CandidateProfile, LanguageEntry, MentionPreferences, StructuredCandidateProfile } from "../types";
import { formatDate } from "../utils";

const WORK_MODELS = ["Remote", "Hybrid", "Onsite"];
const TONES = ["Professional", "Friendly and professional", "Formal", "Confident", "Enthusiastic", "Concise"];
const MENTION_LABELS: Record<keyof MentionPreferences, string> = {
  education: "Education",
  certifications: "Certifications",
  internships: "Internships",
  projects: "Projects",
  customer_facing_experience: "Customer-facing experience",
  technical_skills: "Technical skills",
  career_motivation: "Career motivation",
};

function fileSize(bytes: number) {
  return bytes >= 1_048_576 ? `${(bytes / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function CandidateProfilePage() {
  const [record, setRecord] = useState<CandidateProfile | null>(null);
  const [draft, setDraft] = useState<StructuredCandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();
  const dirty = useMemo(() => Boolean(record && draft && JSON.stringify(draft) !== JSON.stringify(record.profile)), [draft, record]);

  const load = async () => {
    setError("");
    try {
      const value = await api.profile();
      setRecord(value);
      setDraft(structuredClone(value.profile));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load profile");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const warnOnNavigation = (event: MouseEvent) => {
      if (!dirty) return;
      const link = (event.target as Element | null)?.closest("a[href]") as HTMLAnchorElement | null;
      if (link?.origin === window.location.origin && !window.confirm("Discard your unsaved candidate profile changes?")) {
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
  }, [dirty]);

  if (loading) return <LoadingState label="Loading candidate profile" />;
  if (error || !record || !draft) return <ErrorState message={error || "Profile unavailable"} onRetry={load} />;

  const update = <K extends keyof StructuredCandidateProfile>(key: K, value: StructuredCandidateProfile[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  };

  const save = async () => {
    setSaving(true);
    try {
      const value = await api.saveProfile({
        ...draft,
        languages: draft.languages.filter((entry) => entry.language.trim()),
      });
      setRecord(value);
      setDraft(structuredClone(value.profile));
      showToast("Structured candidate profile saved", "success");
      window.dispatchEvent(new CustomEvent("jobbot:refresh"));
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to save profile", "error");
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm("Restore the initial structured profile?")) return;
    try {
      const value = await api.resetProfile();
      setRecord(value);
      setDraft(structuredClone(value.profile));
      showToast("Initial profile restored", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to restore profile", "error");
    }
  };

  const upload = async (file: File) => {
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

  const extract = async () => {
    setExtracting(true);
    try {
      await api.extractProfileFromCV();
      await load();
      showToast("Profile fields extracted from CV", "success");
      window.dispatchEvent(new CustomEvent("jobbot:refresh"));
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to extract CV profile", "error");
    } finally {
      setExtracting(false);
    }
  };

  const updateLanguage = (index: number, patch: Partial<LanguageEntry>) => {
    update("languages", draft.languages.map((entry, current) => current === index ? { ...entry, ...patch } : entry));
  };

  return (
    <>
      <PageHeader
        eyebrow="Candidate intelligence"
        title="Candidate profile"
        description="Structured facts drive filtering and scoring; private CV text provides deeper evidence for Gemini and cover letters."
        actions={<span className="version-pill">Profile version {record.version}</span>}
      />

      <div className="structured-profile-stack">
        <section className="panel profile-section cv-upload-section">
          <div className="section-heading">
            <div><p className="eyebrow">CV source</p><h2>Curriculum vitae</h2></div>
            <FileText size={21} />
          </div>
          <div className="cv-upload-row">
            <div className="cv-file-summary">
              {record.cv ? <><strong>{record.cv.file_name}</strong><span>{fileSize(record.cv.size_bytes)} · Uploaded {formatDate(record.cv.uploaded_at, true)}</span><small>{record.cv.extracted_at ? `Profile extracted ${formatDate(record.cv.extracted_at, true)}` : "Ready for profile extraction"}</small></> : <><strong>No CV uploaded</strong><span>PDF or DOCX, up to 10 MB</span><small>The original file and extracted text stay on this machine.</small></>}
            </div>
            <div className="button-row">
              <input ref={fileInput} className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => event.target.files?.[0] && void upload(event.target.files[0])} />
              <button className="button button-secondary" disabled={uploading} onClick={() => fileInput.current?.click()}><Upload size={16} /> {uploading ? "Uploading…" : record.cv ? "Replace CV" : "Upload CV"}</button>
              <button className="button button-primary" disabled={!record.cv || extracting} onClick={extract}><Sparkles size={16} /> {extracting ? "Extracting…" : "Extract Profile from CV"}</button>
            </div>
          </div>
        </section>

        <section className="panel profile-section">
          <div className="section-heading"><div><p className="eyebrow">Basic information</p><h2>Identity and links</h2></div></div>
          <div className="form-grid profile-form-grid">
            <label>Full name<input value={draft.full_name} onChange={(event) => update("full_name", event.target.value)} autoComplete="name" /></label>
            <label>Email<input type="email" value={draft.email} onChange={(event) => update("email", event.target.value)} autoComplete="email" /></label>
            <label>Current location<input value={draft.current_location} onChange={(event) => update("current_location", event.target.value)} placeholder="Zurich, Switzerland" /></label>
            <label>LinkedIn URL<input type="url" value={draft.linkedin_url} onChange={(event) => update("linkedin_url", event.target.value)} placeholder="https://linkedin.com/in/..." /></label>
            <label>Portfolio / website<input type="url" value={draft.portfolio_url} onChange={(event) => update("portfolio_url", event.target.value)} placeholder="https://..." /></label>
          </div>
        </section>

        <section className="panel profile-section">
          <div className="section-heading"><div><p className="eyebrow">Preferences</p><h2>Career direction</h2></div></div>
          <div className="profile-field-stack">
            <div className="form-grid profile-form-grid">
              <label>Preferred seniority<select value={draft.preferred_seniority} onChange={(event) => update("preferred_seniority", event.target.value)}><option value="">No preference</option><option>Internship</option><option>Entry level / Junior</option><option>Mid level</option><option>Senior</option><option>Lead / Principal</option></select></label>
              <TagInput label="Preferred industries" values={draft.preferred_industries} onChange={(values) => update("preferred_industries", values)} placeholder="Cybersecurity, Cloud…" />
              <TagInput label="Preferred locations" values={draft.preferred_locations} onChange={(values) => update("preferred_locations", values)} placeholder="Zurich, Switzerland" />
            </div>
            <fieldset className="choice-fieldset"><legend className="field-label">Work model preference</legend><div className="inline-check-grid">{WORK_MODELS.map((model) => <CheckChoice key={model} label={model} checked={draft.work_model_preferences.includes(model)} onChange={(checked) => update("work_model_preferences", checked ? [...draft.work_model_preferences, model] : draft.work_model_preferences.filter((value) => value !== model))} />)}</div></fieldset>
          </div>
        </section>

        <section className="panel profile-section">
          <div className="section-heading"><div><p className="eyebrow">Evidence</p><h2>Skills and experience</h2></div></div>
          <div className="profile-field-stack">
            <TagInput label="Skills" values={draft.skills} onChange={(values) => update("skills", values)} placeholder="Python, Azure, Kubernetes…" />
            <TagInput label="Certifications" values={draft.certifications} onChange={(values) => update("certifications", values)} placeholder="Certification name" />
            <div className="form-grid experience-grid">
              <label>Total experience (years)<input type="number" min={0} max={80} step={0.5} value={draft.years_total_experience} onChange={(event) => update("years_total_experience", Number(event.target.value))} /></label>
              <label>Software engineering<input type="number" min={0} max={80} step={0.5} value={draft.years_software_engineering} onChange={(event) => update("years_software_engineering", Number(event.target.value))} /></label>
              <label>Cloud experience<input type="number" min={0} max={80} step={0.5} value={draft.years_cloud_experience} onChange={(event) => update("years_cloud_experience", Number(event.target.value))} /></label>
              <label>Customer-facing<input type="number" min={0} max={80} step={0.5} value={draft.years_customer_facing} onChange={(event) => update("years_customer_facing", Number(event.target.value))} /></label>
            </div>
            <div className="language-editor">
              <span className="field-label">Languages and proficiency</span>
              {draft.languages.map((entry, index) => <div className="language-row" key={index}><input value={entry.language} onChange={(event) => updateLanguage(index, { language: event.target.value })} placeholder="Language" /><input value={entry.proficiency} onChange={(event) => updateLanguage(index, { proficiency: event.target.value })} placeholder="Proficiency (e.g. C1)" /><button className="icon-button" onClick={() => update("languages", draft.languages.filter((_, current) => current !== index))} aria-label="Remove language"><Trash2 size={15} /></button></div>)}
              <AddRowButton label="Add language" onClick={() => update("languages", [...draft.languages, { language: "", proficiency: "" }])} />
            </div>
            <div className="form-grid two-column structured-text-grid">
              <StringListField label="Education" values={draft.education} onChange={(values) => update("education", values)} placeholder="Degree, school, dates" />
              <StringListField label="Work experience" values={draft.work_experience} onChange={(values) => update("work_experience", values)} placeholder="Role, employer, impact" rows={6} />
              <StringListField label="Projects" values={draft.projects} onChange={(values) => update("projects", values)} placeholder="Project and relevant outcome" />
              <label>Professional summary<textarea rows={6} value={draft.professional_summary} onChange={(event) => update("professional_summary", event.target.value)} placeholder="Concise factual overview of your background" /></label>
            </div>
          </div>
        </section>

        <section className="panel profile-section">
          <div className="section-heading"><div><p className="eyebrow">Application writing</p><h2>Cover letter profile</h2></div></div>
          <div className="profile-field-stack">
            <label>Base cover letter<textarea rows={12} value={draft.base_cover_letter} onChange={(event) => update("base_cover_letter", event.target.value)} placeholder="Enter the truthful base letter the app should tailor for each role…" /><small className="field-help">Required before generating a tailored cover letter.</small></label>
            <label>Career motivation<textarea rows={4} value={draft.career_motivation} onChange={(event) => update("career_motivation", event.target.value)} /></label>
            <div className="form-grid two-column structured-text-grid">
              <StringListField label="Key achievements" values={draft.key_achievements} onChange={(values) => update("key_achievements", values)} placeholder="Specific, truthful achievement" />
              <StringListField label="Projects to highlight" values={draft.projects_to_highlight} onChange={(values) => update("projects_to_highlight", values)} placeholder="Project to mention when relevant" />
            </div>
            <label className="tone-select">Preferred writing tone<select value={draft.writing_tone} onChange={(event) => update("writing_tone", event.target.value)}>{TONES.map((tone) => <option key={tone}>{tone}</option>)}</select></label>
            <fieldset className="choice-fieldset"><legend className="field-label">Include when relevant</legend><div className="mention-grid">{(Object.keys(MENTION_LABELS) as (keyof MentionPreferences)[]).map((key) => <CheckChoice key={key} label={MENTION_LABELS[key]} checked={draft.mention_preferences[key]} onChange={(checked) => update("mention_preferences", { ...draft.mention_preferences, [key]: checked })} />)}</div></fieldset>
          </div>
        </section>

        <section className="profile-save-bar panel">
          <div><strong>{dirty ? "Unsaved profile changes" : "Profile is up to date"}</strong><span>Last saved {formatDate(record.updated_at, true)}</span></div>
          <div className="button-row">
            <button className="button button-ghost" disabled={!dirty} onClick={() => setDraft(structuredClone(record.profile))}><RefreshCcw size={16} /> Discard changes</button>
            <button className="button button-secondary" onClick={reset}><ShieldCheck size={16} /> Restore initial profile</button>
            <button className="button button-primary" disabled={!dirty || saving} onClick={save}><Save size={16} /> {saving ? "Saving…" : "Save profile"}</button>
          </div>
        </section>
      </div>
    </>
  );
}
