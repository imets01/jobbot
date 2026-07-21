import { RotateCcw, Save, ShieldCheck, Sparkles, Undo2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useToast } from "../components/ToastProvider";
import { ErrorState, LoadingState, PageHeader } from "../components/Ui";
import type { CandidateProfile } from "../types";
import { formatDate } from "../utils";

export function CandidateProfilePage() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { showToast } = useToast();
  const dirty = useMemo(() => Boolean(profile && draft !== profile.content), [draft, profile]);

  const load = async () => {
    setError("");
    try {
      const value = await api.profile();
      setProfile(value);
      setDraft(value.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load profile");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const warnOnNavigation = (event: MouseEvent) => {
      if (!dirty) return;
      const target = event.target as Element | null;
      const link = target?.closest("a[href]") as HTMLAnchorElement | null;
      if (!link || link.origin !== window.location.origin) return;
      if (!window.confirm("Discard your unsaved candidate profile changes?")) {
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

  const save = async () => {
    setSaving(true);
    try {
      const value = await api.saveProfile(draft);
      setProfile(value);
      setDraft(value.content);
      showToast("Candidate profile saved. Future analyses will use it.", "success");
      window.dispatchEvent(new CustomEvent("jobbot:refresh"));
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to save profile", "error");
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm("Restore the profile originally defined in analyzer.py?")) return;
    try {
      const value = await api.resetProfile();
      setProfile(value);
      setDraft(value.content);
      showToast("Default candidate profile restored", "success");
      window.dispatchEvent(new CustomEvent("jobbot:refresh"));
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Unable to restore profile", "error");
    }
  };

  if (loading) return <LoadingState label="Loading candidate profile" />;
  if (error || !profile) return <ErrorState message={error || "Profile unavailable"} onRetry={load} />;

  return (
    <>
      <PageHeader eyebrow="Gemini context" title="Candidate profile" description="Define the background, preferences, and constraints Gemini should use when evaluating each job." />
      <div className="profile-layout">
        <section className="panel profile-editor-panel">
          <div className="section-heading">
            <div><p className="eyebrow">Profile editor</p><h2>Your matching criteria</h2></div>
            <span className="version-pill">Version {profile.version}</span>
          </div>
          <label className="profile-textarea-label">
            Candidate profile
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={24} aria-describedby="profile-help" />
          </label>
          <div className="editor-footer">
            <p id="profile-help">{draft.length.toLocaleString()} characters · Last saved {formatDate(profile.updated_at, true)}</p>
            <div className="button-row">
              <button className="button button-ghost" disabled={!dirty} onClick={() => setDraft(profile.content)}><Undo2 size={16} /> Cancel</button>
              <button className="button button-secondary" onClick={reset}><RotateCcw size={16} /> Restore default</button>
              <button className="button button-primary" disabled={!dirty || saving || draft.trim().length < 20} onClick={save}><Save size={16} /> {saving ? "Saving…" : "Save profile"}</button>
            </div>
          </div>
          {dirty && <div className="unsaved-banner">You have unsaved changes.</div>}
        </section>

        <aside className="profile-guidance">
          <article className="panel guidance-card">
            <span className="guidance-icon"><Sparkles size={20} /></span>
            <h3>Future analyses only</h3>
            <p>Saving does not rewrite history. Existing verdicts keep the exact profile snapshot that produced them.</p>
          </article>
          <article className="panel guidance-card">
            <span className="guidance-icon"><ShieldCheck size={20} /></span>
            <h3>Private by design</h3>
            <p>Your profile and API key remain on the backend. The browser receives only profile text needed for editing.</p>
          </article>
          <article className="panel guidance-card">
            <h3>Writing a useful profile</h3>
            <ul><li>State target roles and seniority.</li><li>Name concrete technical skills.</li><li>Describe deal-breakers such as pure sales.</li><li>Keep constraints explicit and measurable.</li></ul>
          </article>
        </aside>
      </div>
    </>
  );
}
