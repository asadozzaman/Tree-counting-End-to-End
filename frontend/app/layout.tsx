import { Metadata } from "next";
import "./globals.css";
import TopNav from "./components/top-nav";

export const metadata: Metadata = {
  title: "Tree Counting SaaS",
  description: "Computer vision tree counting dashboard"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TopNav />
        <main className="app-shell">{children}</main>
      </body>
    </html>
  );
}