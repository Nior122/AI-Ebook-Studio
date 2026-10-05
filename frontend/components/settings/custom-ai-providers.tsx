"use client";

// Manage user-supplied custom AI providers (bring-your-own endpoint/model/key).
//
// Lets a user add OpenAI-compatible endpoints, or their own Anthropic / Gemini
// keys, along with the model ids those providers expose. API keys are encrypted
// server-side and never returned; the form only ever sends them, never reads
// them back. After any change, `onChanged` fires so the parent can refresh the
// provider/model dropdowns elsewhere on the page.

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Checkbox, Input, Select } from "@/components/ui/input";
import {
  aiApi,
  type CustomAIProvider,
  type CustomAIProviderInput,
} from "@/lib/api/ai";

type ProviderType = "openai_compatible" | "anthropic" | "gemini";

const PROVIDER_TYPE_OPTIONS: { value: ProviderType; label: string }[] = [
  { value: "openai_compatible", label: "OpenAI-compatible endpoint" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Google Gemini" },
];

const TYPE_LABEL: Record<ProviderType, string> = {
  openai_compatible: "OpenAI-compatible",
  anthropic: "Anthropic",
  gemini: "Gemini",
};

interface FormState {
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key: string;
  model_ids: string; // comma-separated in the form
  default_model: string;
  supports_structured_output: boolean;
  is_active: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  provider_type: "openai_compatible",
  base_url: "",
  api_key: "",
  model_ids: "",
  default_model: "",
  supports_structured_output: true,
  is_active: true,
};

export function CustomAIProvidersCard({ onChanged }: { onChanged?: () => void }) {
  const [rows, setRows] = useState<CustomAIProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Form state. `editingId` is null when creating.
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // Per-row test feedback.
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    try {
      const data = await aiApi.listCustomProviders();
      setRows(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load custom providers.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
    setError(null);
    setNotice(null);
  }

  function openEdit(row: CustomAIProvider) {
    setEditingId(row.id);
    setForm({
      name: row.name,
      provider_type: row.provider_type,
      base_url: row.base_url ?? "",
      api_key: "", // never prefill secrets
      model_ids: row.model_ids.join(", "),
      default_model: row.default_model ?? "",
      supports_structured_output: row.supports_structured_output,
      is_active: row.is_active,
    });
    setFormOpen(true);
    setError(null);
    setNotice(null);
  }

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSave() {
    setSaving(true);
    setError(null);
    setNotice(null);
    const input: CustomAIProviderInput = {
      name: form.name.trim(),
      provider_type: form.provider_type,
      base_url:
        form.provider_type === "openai_compatible" ? form.base_url.trim() : null,
      model_ids: form.model_ids
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      default_model: form.default_model.trim() || null,
      supports_structured_output: form.supports_structured_output,
      is_active: form.is_active,
    };
    // Only send a key when the user typed one (keeps existing key on edit otherwise).
    if (form.api_key.trim()) input.api_key = form.api_key.trim();

    try {
      if (editingId) {
        await aiApi.updateCustomProvider(editingId, input);
        setNotice("Custom provider updated.");
      } else {
        await aiApi.createCustomProvider(input);
        setNotice("Custom provider added.");
      }
      setFormOpen(false);
      await refresh();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save custom provider.");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(row: CustomAIProvider) {
    if (!confirm(`Delete custom provider "${row.name}"?`)) return;
    setError(null);
    setNotice(null);
    try {
      await aiApi.deleteCustomProvider(row.id);
      setNotice(`Deleted "${row.name}".`);
      await refresh();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete provider.");
    }
  }

  async function onTest(row: CustomAIProvider) {
    setTestingId(row.id);
    setTestResult((r) => ({ ...r, [row.id]: "" }));
    try {
      const res = await aiApi.testCustomProvider(row.id);
      setTestResult((r) => ({
        ...r,
        [row.id]: res.ok
          ? `✓ Connected (${res.model ?? "default"})${res.reply ? ` — "${res.reply}"` : ""}`
          : `✗ Failed: ${res.error ?? "no response"}`,
      }));
    } catch (e) {
      setTestResult((r) => ({
        ...r,
        [row.id]: `✗ ${e instanceof Error ? e.message : "Test failed"}`,
      }));
    } finally {
      setTestingId(null);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Custom AI providers</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Add your own OpenAI-compatible endpoint, or your own Anthropic / Gemini key, with any
            models it supports. Keys are stored encrypted.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={openCreate}>
          + Add provider
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-600">
            {notice}
          </p>
        ) : null}

        {formOpen ? (
          <div className="space-y-4 rounded-md border border-border p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name" htmlFor="cp-name">
                <Input
                  id="cp-name"
                  value={form.name}
                  placeholder="e.g. My OpenRouter"
                  onChange={(e) => setField("name", e.target.value)}
                />
              </Field>
              <Field label="Provider type" htmlFor="cp-type">
                <Select
                  id="cp-type"
                  value={form.provider_type}
                  onChange={(e) => setField("provider_type", e.target.value as ProviderType)}
                >
                  {PROVIDER_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            {form.provider_type === "openai_compatible" ? (
              <Field
                label="Base URL"
                htmlFor="cp-base-url"
                hint="OpenAI Chat-Completions endpoint, e.g. https://openrouter.ai/api/v1"
              >
                <Input
                  id="cp-base-url"
                  value={form.base_url}
                  placeholder="https://…"
                  onChange={(e) => setField("base_url", e.target.value)}
                />
              </Field>
            ) : null}

            <Field
              label={editingId ? "API key (leave blank to keep current)" : "API key"}
              htmlFor="cp-key"
              hint="Encrypted on the server. Never shown again after saving."
            >
              <Input
                id="cp-key"
                type="password"
                autoComplete="new-password"
                value={form.api_key}
                placeholder={editingId ? "••••••••" : "sk-…"}
                onChange={(e) => setField("api_key", e.target.value)}
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Model ids"
                htmlFor="cp-models"
                hint="Comma-separated, e.g. openai/gpt-4o-mini, anthropic/claude-3.5-sonnet"
              >
                <Input
                  id="cp-models"
                  value={form.model_ids}
                  placeholder="model-a, model-b"
                  onChange={(e) => setField("model_ids", e.target.value)}
                />
              </Field>
              <Field label="Default model" htmlFor="cp-default" hint="Optional; defaults to the first model.">
                <Input
                  id="cp-default"
                  value={form.default_model}
                  placeholder="openai/gpt-4o-mini"
                  onChange={(e) => setField("default_model", e.target.value)}
                />
              </Field>
            </div>

            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={form.supports_structured_output}
                  onChange={(e) => setField("supports_structured_output", e.target.checked)}
                />
                Supports structured (JSON) output
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={form.is_active}
                  onChange={(e) => setField("is_active", e.target.checked)}
                />
                Active
              </label>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setFormOpen(false)} disabled={saving}>
                Cancel
              </Button>
              <Button onClick={onSave} disabled={saving}>
                {saving ? "Saving…" : editingId ? "Update provider" : "Add provider"}
              </Button>
            </div>
          </div>
        ) : null}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading custom providers…</p>
        ) : rows.length === 0 && !formOpen ? (
          <p className="text-sm text-muted-foreground">
            No custom providers yet. Add one to use your own models and API keys.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {rows.map((row) => (
              <li key={row.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{row.name}</span>
                    <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
                      {TYPE_LABEL[row.provider_type]}
                    </span>
                    {!row.is_active ? (
                      <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
                        inactive
                      </span>
                    ) : null}
                    {!row.has_key ? (
                      <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-600">
                        no key
                      </span>
                    ) : null}
                  </div>
                  {row.base_url ? (
                    <p className="truncate text-xs text-muted-foreground">{row.base_url}</p>
                  ) : null}
                  <p className="text-xs text-muted-foreground">
                    {row.model_ids.join(", ") || "no models"}
                  </p>
                  {testResult[row.id] ? (
                    <p className="mt-1 text-xs text-muted-foreground">{testResult[row.id]}</p>
                  ) : null}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onTest(row)}
                    disabled={testingId === row.id}
                  >
                    {testingId === row.id ? "Testing…" : "Test"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>
                    Edit
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => onDelete(row)}>
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
