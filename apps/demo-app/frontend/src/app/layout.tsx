import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Demo App — AI-Native DevOps/SRE Platform",
  description:
    "Observable demo workload: health and readiness status plus a small items inventory backed by the FastAPI demo service.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <div className="container">
            <p className="eyebrow">AI-Native DevOps / SRE Platform</p>
            <h1>Demo application</h1>
            <p className="lede">
              A realistic target workload for the platform&apos;s observe → detect → diagnose →
              remediate loop.
            </p>
          </div>
        </header>
        <main id="main" className="container">
          {children}
        </main>
        <footer className="site-footer">
          <div className="container">
            <p>
              Correlation IDs shown in the UI join frontend activity to backend logs, metrics and
              traces.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
