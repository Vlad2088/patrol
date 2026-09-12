// Layout: сайдбар + контент + колокольчик уведомлений
import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";

const nav = [
  { to: "/", label: "Мониторинг", end: true },
  { to: "/patrols", label: "Обходы" },
  { to: "/objects", label: "Объекты" },
  { to: "/routes", label: "Маршруты и точки" },
  { to: "/shifts", label: "Смены" },
  { to: "/guards", label: "Охранники" },
  { to: "/reports", label: "Отчёты" },
  { to: "/audit", label: "Аудит" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { data: violations } = useQuery({
    queryKey: ["notifications"],
    queryFn: api.notifications,
    refetchInterval: 60_000,
  });
  const count = violations?.length ?? 0;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">Patrol</div>
        <nav>
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user">{user?.full_name}</div>
          <button onClick={logout} className="btn-ghost">Выйти</button>
        </div>
      </aside>
      <main className="content">
        <header className="topbar">
          <div className="bell" title="Нарушения">
            🔔 {count > 0 && <span className="badge">{count}</span>}
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
