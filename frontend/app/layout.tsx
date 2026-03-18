import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tree Counting SaaS",
  description: "Tree counting platform scaffold"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
