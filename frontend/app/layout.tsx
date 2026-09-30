import type { Metadata, Viewport } from "next";
import { Barlow, Oswald } from "next/font/google";
import "./globals.css";

const display = Oswald({ subsets: ["latin"], variable: "--font-display" });
const body = Barlow({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Liga de la Mesa",
  description: "Asistente de mesa para una liga privada de Blood Bowl",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#120d0b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={`${display.variable} ${body.variable} overflow-x-hidden font-body antialiased`}>{children}</body>
    </html>
  );
}
