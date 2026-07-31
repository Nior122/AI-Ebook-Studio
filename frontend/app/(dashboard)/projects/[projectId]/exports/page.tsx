import { redirect } from "next/navigation";

// Consolidated into the unified workspace — this route now points there so
// old links and bookmarks keep working.

export default async function RedirectPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  redirect(`/workspace/${projectId}?tool=export`);
}
