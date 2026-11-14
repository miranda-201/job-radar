import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import AuthPage from "./components/AuthPage";
import Board from "./components/Board";
import JobFeed from "./components/JobFeed";
import Targets from "./components/Targets";
import type { User } from "./types";

type Tab = "board" | "radar" | "targets";
const TABS: { id: Tab; label: string }[] = [
  { id: "board", label: "Board" },
  { id: "radar", label: "Job Radar" },
  { id: "targets", label: "Watched Companies" },
];

function tabFromHash(): Tab {
  const h = window.location.hash.replace("#", "");
  return (TABS.some((t) => t.id === h) ? h : "board") as Tab;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(Boolean(getToken()));
  const [tab, setTab] = useState<Tab>(tabFromHash);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (getToken()) {
      api
        .me()
        .then(setUser)
        .catch(logout)
        .finally(() => setBooting(false));
    }
  }, [logout]);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (booting) return <div className="center muted">Loading…</div>;
  if (!user)
    return (
      <AuthPage
        onAuthenticated={(token, u) => {
          setToken(token);
          setUser(u);
        }}
      />
    );

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            ◎
          </span>
          JobRadar
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <a key={t.id} href={`#${t.id}`} className={tab === t.id ? "tab active" : "tab"}>
              {t.label}
            </a>
          ))}
        </nav>
        <div className="user">
          <span className="muted">{user.displayName}</span>
          <button className="ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="content">
        {tab === "board" && <Board />}
        {tab === "radar" && <JobFeed />}
        {tab === "targets" && <Targets />}
      </main>
    </div>
  );
}
