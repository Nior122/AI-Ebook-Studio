"use client";

// Account settings page. Shows the signed-in user, provides theme toggle,
// profile editing, notification preferences, and export/writing preferences.

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Textarea, Select, Checkbox } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useUser } from "@clerk/nextjs";

function useTheme() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      window.localStorage.setItem("ebook:theme", next ? "dark" : "light");
    } catch {
      /* ignore */
    }
  }
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("ebook:theme");
      if (saved === "dark") document.documentElement.classList.add("dark");
    } catch {
      /* ignore */
    }
  }, []);
  return { dark, toggle };
}

function useLocalPrefs() {
  const [prefs, setPrefs] = useState<Record<string, unknown>>({});
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("ebook:prefs");
      if (stored) setPrefs(JSON.parse(stored));
    } catch {
      /* ignore */
    }
  }, []);
  function save(key: string, value: unknown) {
    setPrefs((prev) => {
      const next = { ...prev, [key]: value };
      try {
        window.localStorage.setItem("ebook:prefs", JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }
  return { prefs, save };
}

export default function SettingsPage() {
  const { user } = useUser();
  const { dark, toggle } = useTheme();
  const { prefs, save } = useLocalPrefs();
  const toast = useToast();

  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  useEffect(() => {
    if (user) {
      setDisplayName(user.fullName ?? "");
    }
  }, [user]);

  async function saveProfile() {
    if (!user) return;
    setSavingProfile(true);
    try {
      await user.update({ firstName: displayName.split(" ")[0], lastName: displayName.split(" ").slice(1).join(" ") });
      if (bio) {
        try {
          (user as any).unsafeUpdateMetadata?.({ bio });
        } catch {
          /* metadata update may not be available in all Clerk setups */
        }
      }
      toast({ title: "Profile updated", variant: "success" });
    } catch (err) {
      toast({ title: "Update failed", description: err instanceof Error ? err.message : "Unknown error", variant: "error" });
    } finally {
      setSavingProfile(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your account and preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Display name" htmlFor="display-name">
            <Input
              id="display-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name"
            />
          </Field>
          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              value={user?.primaryEmailAddress?.emailAddress ?? ""}
              disabled
            />
          </Field>
          <Field label="Bio" htmlFor="bio" hint="Shown on your author profile.">
            <Textarea
              id="bio"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Tell readers about yourself..."
              rows={3}
            />
          </Field>
          <Button onClick={saveProfile} disabled={savingProfile || !displayName}>
            {savingProfile ? "Saving..." : "Save profile"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">Switch between light and dark mode.</p>
          <Button variant="outline" onClick={toggle}>
            {dark ? "Light mode" : "Dark mode"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Export Preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="Default export format" htmlFor="default-format">
            <Select
              id="default-format"
              value={(prefs.defaultExportFormat as string) ?? "docx"}
              onChange={(e) => save("defaultExportFormat", e.target.value)}
            >
              <option value="docx">DOCX (Word)</option>
              <option value="pdf">PDF</option>
              <option value="epub">EPUB</option>
            </Select>
          </Field>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(prefs.includeFrontMatter as boolean) ?? true}
              onChange={(e) => save("includeFrontMatter", e.target.checked)}
            />
            <span className="text-sm">Include front matter (title page)</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(prefs.includeToc as boolean) ?? true}
              onChange={(e) => save("includeToc", e.target.checked)}
            />
            <span className="text-sm">Include table of contents</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(prefs.includeBackMatter as boolean) ?? false}
              onChange={(e) => save("includeBackMatter", e.target.checked)}
            />
            <span className="text-sm">Include back matter (about author)</span>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Writing Preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="Default writing language" htmlFor="writing-lang">
            <Select
              id="writing-lang"
              value={(prefs.writingLanguage as string) ?? "en"}
              onChange={(e) => save("writingLanguage", e.target.value)}
            >
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="pt">Portuguese</option>
              <option value="it">Italian</option>
              <option value="nl">Dutch</option>
              <option value="ja">Japanese</option>
              <option value="zh">Chinese</option>
            </Select>
          </Field>
          <Field label="Default writing style" htmlFor="writing-style">
            <Input
              id="writing-style"
              value={(prefs.writingStyle as string) ?? ""}
              onChange={(e) => save("writingStyle", e.target.value)}
              placeholder="e.g. conversational, authoritative"
            />
          </Field>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(prefs.autosave as boolean) ?? true}
              onChange={(e) => save("autosave", e.target.checked)}
            />
            <span className="text-sm">Enable autosave while editing</span>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(prefs.notifyExportReady as boolean) ?? true}
              onChange={(e) => save("notifyExportReady", e.target.checked)}
            />
            <span className="text-sm">Notify when exports are ready</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(prefs.notifyTranslationDone as boolean) ?? true}
              onChange={(e) => save("notifyTranslationDone", e.target.checked)}
            />
            <span className="text-sm">Notify when translations complete</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(prefs.notifyMarketingTips as boolean) ?? false}
              onChange={(e) => save("notifyMarketingTips", e.target.checked)}
            />
            <span className="text-sm">Marketing tips and best practices</span>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Account Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Account ID</span>
            <span className="font-mono text-xs">{user?.id ?? "—"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Email verification</span>
            {user?.primaryEmailAddress?.verification?.status === "verified" ? (
              <Badge variant="success">Verified</Badge>
            ) : (
              <Badge variant="warning">Pending</Badge>
            )}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Plan</span>
            <Badge variant="default">Free</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
