import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Inter, JetBrains_Mono } from "next/font/google";
import { HealthCheck } from "../components/HealthCheck";

const display = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "LogVision | AI-powered Log Intelligence Assistant",
  description: "Chat-first log analysis with AI insights",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full dark">
      <body className={`${display.variable} ${mono.variable} h-full bg-[#0b0b0c] text-text-primary antialiased`}>
        <Providers>
          {children}
          <HealthCheck />
        </Providers>
      </body>
    </html>
  );
}
