import type { NextConfig } from "next";

const backend = process.env.CPSOLVE_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  // Compression must be OFF for this app.
  //
  // The solver streams its progress over Server-Sent Events. When Next gzips a
  // proxied response it buffers the whole body first, so every stage event
  // arrives at once, at the end — the live pipeline silently stops being live
  // and the user stares at a spinner for the entire solve. Static assets are
  // served compressed by the CDN or reverse proxy in front of this app, so
  // nothing is lost by disabling it here.
  compress: false,

  // In development the browser talks to one origin and this forwards /api to
  // the engine. In production, set NEXT_PUBLIC_API_URL so the browser calls the
  // engine directly and no proxy sits in the streaming path.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
