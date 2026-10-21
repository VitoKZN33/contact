/** @type {import('next').NextConfig} */
const nextConfig = {
  // Mini App не нужен SSR: собираем статический сайт, его раздаёт Nginx
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
  reactStrictMode: true,
};

export default nextConfig;
