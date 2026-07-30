import type { Metadata } from "next";
import "../styles/globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: {
    default: "AI Ebook Studio",
    template: "%s | AI Ebook Studio",
  },
  description: "Production SaaS foundation for an AI ebook creation platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased" suppressHydrationWarning>
        <ClerkProvider>
          <Providers>{children}</Providers>
        </ClerkProvider>
      </body>
    </html>
  );
}
