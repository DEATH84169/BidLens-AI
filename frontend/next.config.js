/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Never send a fork user's uploaded bids or officer key to the upstream deployment.
    const backendUrl = process.env.BACKEND_PROXY_URL || "http://127.0.0.1:8000";
    return ["audit", "document", "review", "system"].map((prefix) => ({
      source: `/${prefix}/:path*`,
      destination: `${backendUrl}/${prefix}/:path*`,
    }));
  },
};
module.exports = nextConfig;
