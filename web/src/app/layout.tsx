import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Culture",
  description: "Culture management platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <nav className="border-b bg-background">
          <div className="flex h-14 items-center px-6 gap-6">
            <a href="/" className="font-bold text-lg">
              Culture
            </a>
            <a
              href="/sites"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Sites
            </a>
            <a
              href="/releases"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Releases
            </a>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
