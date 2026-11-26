import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const medeo = localFont({ src: "./fonts/MedeoSansVariable.woff2", weight: "100 900", variable: "--font-medeo", display: "swap" });

export const metadata: Metadata = {
  title: "Markin",
  description: "Markin — проверка на плагиат и ИИ-детекцию",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={medeo.variable}>
      <body className="bg-canvas text-gray-900 font-sans antialiased">{children}</body>
    </html>
  );
}
