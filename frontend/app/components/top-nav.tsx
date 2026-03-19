"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { clearToken, getToken } from "../lib/auth";

export default function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setHasToken(Boolean(getToken()));
  }, [pathname]);

  const links = useMemo(
    () => [
      { href: "/projects", label: "Projects" },
      { href: "/login", label: "Login" },
      { href: "/register", label: "Register" }
    ],
    []
  );

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link href="/" className="brand">
          Tree Counting SaaS
        </Link>
        <nav className="nav-links">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className={`nav-link ${pathname === link.href ? "active" : ""}`}>
              {link.label}
            </Link>
          ))}
          {hasToken && (
            <button
              type="button"
              className="ghost-btn"
              onClick={() => {
                clearToken();
                router.push("/login");
              }}
            >
              Logout
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}