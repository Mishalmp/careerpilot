import type { Metadata } from "next";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "CareerPilot", template: "%s · CareerPilot" },
  description: "Job tracker, interview prep and practice in one place",
};

// suppressHydrationWarning: public/theme-init.js adds the `dark` class and data-density to <html>
// before React hydrates, so the attributes legitimately differ from the server markup.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        {/* Blocking on purpose: it must run before first paint to avoid a flash of the wrong theme. */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="/theme-init.js" />
      </head>
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
