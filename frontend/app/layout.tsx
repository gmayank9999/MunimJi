import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { MunimjiMascot } from "@/components/MunimjiMascot";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MunimJi",
  description: "Autonomous FinOps · Governed by Swytchcode",
};

// Runs before hydration so the page never flashes the wrong theme: reads the saved
// choice (falls back to the visitor's OS preference), then sets it on <html> directly.
const THEME_INIT_SCRIPT = `
  try {
    var stored = localStorage.getItem("munimji-theme");
    var theme = stored === "light" || stored === "dark"
      ? stored
      : (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}>
        {children}
        <MunimjiMascot />
      </body>
    </html>
  );
}
