/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8003",
      },
      {
        protocol: "http",
        hostname: "backend",
        port: "8003",
      },
    ],
  },
};

module.exports = nextConfig;
