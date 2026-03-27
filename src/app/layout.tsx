import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIphaWatch",
  description: "AI-powered equity intelligence for buy-side analysts",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b border-gray-200 bg-white px-6 py-3">
          <h1 className="text-lg font-semibold text-gray-800">AIphaWatch</h1>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
