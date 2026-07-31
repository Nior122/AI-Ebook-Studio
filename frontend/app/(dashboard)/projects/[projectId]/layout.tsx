// Minimal passthrough layout for legacy /projects/[projectId]/* URLs.
// All of those routes now redirect into the unified workspace
// (/workspace/[projectId]), so no project fetching happens here.

export default function LegacyProjectLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
