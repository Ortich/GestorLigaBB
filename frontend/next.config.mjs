/** @type {import('next').NextConfig} */
const apiTarget = process.env.API_URL || "http://127.0.0.1:8000";

const isProduction = process.env.NODE_ENV === "production";

const nextConfig = {
  // En produccion se exporta estatico y lo sirve FastAPI desde `frontend/out`.
  // En `next dev` se mantiene el servidor de Next para poder proxear la API.
  output: isProduction ? "export" : undefined,
  trailingSlash: true,
  images: { unoptimized: true },
  ...(isProduction
    ? {}
    : {
        async rewrites() {
          return [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }];
        },
      }),
};

export default nextConfig;
