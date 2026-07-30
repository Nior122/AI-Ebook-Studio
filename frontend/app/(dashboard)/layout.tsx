// Dashboard route-group layout. Wraps every authenticated page (dashboard,
// projects, settings, project workspace) with the route guard and the app shell.

import { Protected } from "@/components/layouts/protected";
import { AppShell } from "@/components/layouts/app-shell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <Protected>
      <AppShell>{children}</AppShell>
    </Protected>
  );
}
