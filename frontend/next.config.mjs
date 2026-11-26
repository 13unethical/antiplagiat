/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async redirects() {
    return [
      { source: "/profile", destination: "/settings", permanent: true },
      { source: "/admin/settings", destination: "/settings", permanent: true },
    ];
  },
};

export default nextConfig;
