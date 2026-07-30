"use client";

// AI provider settings foundation.
//
// Lets a user choose their preferred AI provider, model, fallback, temperature,
// writing style and language. Selections are saved via the backend
// /ai/preferences endpoint (which stores *selections only* — never raw keys).
// This is the UI foundation; richer model-selection UX can build on the
// /ai/capabilities data already returned by the API.

import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Label, Select } from "@/components/ui/input";

import { aiApi, type AIModelInfo, type AIProviderInfo } from "@/lib/api/ai";

const WRITING_STYLES = [
  "Conversational",
  "Authoritative",
  "Narrative",
  "Minimal",
  "Academic",
  "Playful",
];
const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "pt", label: "Portuguese" },
  { code: "ja", label: "Japanese" },
  { code: "zh", label: "Chinese" },
];

export default function AISettingsPage() {
  const [providers, setProviders] = useState<AIProviderInfo[]>([]);
  const [models, setModels] = useState<AIModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [preferredProvider, setPreferredProvider] = useState<string>("");
  const [preferredModel, setPreferredModel] = useState<string>("");
  const [fallbackProvider, setFallbackProvider] = useState<string>("");
  const [fallbackModel, setFallbackModel] = useState<string>("");
  const [temperature, setTemperature] = useState<number>(0.7);
  const [writingStyle, setWritingStyle] = useState<string>("");
  const [language, setLanguage] = useState<string>("en");

  // Models available for the currently-selected preferred provider.
  const preferredModels = useMemo(
    () => models.filter((m) => m.provider === preferredProvider),
    [models, preferredProvider],
  );
  const fallbackModels = useMemo(
    () => models.filter((m) => m.provider === fallbackProvider),
    [models, fallbackProvider],
  );

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [ps, ms, prefs] = await Promise.all([
          aiApi.listProviders(),
          aiApi.listModels(),
          aiApi.getPreferences().catch(() => null),
        ]);
        if (!active) return;
        setProviders(ps);
        setModels(ms);
        if (prefs) {
          setPreferredProvider(prefs.preferred_provider ?? ps[0]?.name ?? "");
          setPreferredModel(prefs.preferred_model ?? "");
          setFallbackProvider(prefs.fallback_provider ?? "");
          setFallbackModel(prefs.fallback_model ?? "");
          setTemperature(prefs.temperature ?? 0.7);
          setWritingStyle(prefs.default_writing_style ?? "");
          setLanguage(prefs.default_language ?? "en");
        } else if (ps[0]) {
          setPreferredProvider(ps[0].name);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load AI settings.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function onSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await aiApi.updatePreferences({
        preferred_provider: preferredProvider || null,
        preferred_model: preferredModel || null,
        fallback_provider: fallbackProvider || null,
        fallback_model: fallbackModel || null,
        temperature,
        default_writing_style: writingStyle || null,
        default_language: language,
      });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save AI settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading AI settings…</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">AI Provider</h1>
        <p className="text-sm text-muted-foreground">
          Choose which AI provider and model power your writing features. Your API keys stay on the
          server — this screen only stores your selections.
        </p>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-600">
          AI preferences saved.
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Provider &amp; Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Preferred provider" htmlFor="preferred-provider">
            <Select
              id="preferred-provider"
              value={preferredProvider}
              onChange={(e) => {
                setPreferredProvider(e.target.value);
                setPreferredModel("");
              }}
            >
              <option value="">Select a provider…</option>
              {providers.map((p) => (
                <option key={p.name} value={p.name} disabled={!p.available}>
                  {p.name}
                  {p.available ? "" : " (not configured)"}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Preferred model" htmlFor="preferred-model">
            <Select
              id="preferred-model"
              value={preferredModel}
              onChange={(e) => setPreferredModel(e.target.value)}
            >
              <option value="">Select a model…</option>
              {preferredModels.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.display_name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Fallback provider" htmlFor="fallback-provider" hint="Used automatically if the primary fails.">
            <Select
              id="fallback-provider"
              value={fallbackProvider}
              onChange={(e) => {
                setFallbackProvider(e.target.value);
                setFallbackModel("");
              }}
            >
              <option value="">None</option>
              {providers.map((p) => (
                <option key={p.name} value={p.name} disabled={!p.available}>
                  {p.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Fallback model" htmlFor="fallback-model">
            <Select
              id="fallback-model"
              value={fallbackModel}
              onChange={(e) => setFallbackModel(e.target.value)}
            >
              <option value="">Select a model…</option>
              {fallbackModels.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.display_name}
                </option>
              ))}
            </Select>
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Generation &amp; Writing</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label={`Temperature: ${temperature.toFixed(2)}`} htmlFor="temperature">
            <Input
              id="temperature"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
            />
          </Field>

          <Field label="Default writing style" htmlFor="writing-style">
            <Select id="writing-style" value={writingStyle} onChange={(e) => setWritingStyle(e.target.value)}>
              <option value="">Default</option>
              {WRITING_STYLES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Default language" htmlFor="language">
            <Select id="language" value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </Select>
          </Field>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save AI settings"}
        </Button>
      </div>
    </div>
  );
}
