import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // this is a plain Next.js app, not meant to auto-generate AI agent
  // guidance files (AGENTS.md/CLAUDE.md) into web/ on every `next dev`.
  agentRules: false,
  // the repo root has its own lockfile-free layout (Python backend); web/ is
  // the only Node project, so pin Turbopack's root here instead of letting
  // it warn about/guess from sibling lockfiles.
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
