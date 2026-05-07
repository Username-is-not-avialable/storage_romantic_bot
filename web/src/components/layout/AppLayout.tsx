import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { logout } from "@/api/auth";
import { ME_QUERY_KEY, useMe } from "@/auth/useMe";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "text-sm rounded-md px-3 py-2 transition-colors",
    isActive ? "bg-secondary text-secondary-foreground" : "text-muted-foreground hover:text-foreground",
  );

export function AppLayout() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: me } = useMe();

  async function onLogout() {
    try {
      await logout();
    } catch {
      // сеанс всё равно сбросим в UI
    }
    qc.setQueryData(ME_QUERY_KEY, null);
    navigate("/login");
  }

  return (
    <div className="min-h-svh flex flex-col">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <nav className="flex flex-wrap items-center gap-1">
            <NavLink to="/" className={linkClass} end>
              Главная
            </NavLink>
            <NavLink to="/catalog" className={linkClass}>
              Каталог
            </NavLink>
            {me ? (
              <>
                <NavLink to="/me" className={linkClass} end>
                  Мой склад
                </NavLink>
                <NavLink to="/requests/new" className={linkClass}>
                  Заявка на выдачу
                </NavLink>
                <NavLink to="/me/return-requests/new" className={linkClass}>
                  Заявка на возврат
                </NavLink>
                {(me.role === "manager" || me.role === "admin") && (
                  <>
                    <NavLink to="/manager/requests" className={linkClass}>
                      Заявки (завснар)
                    </NavLink>
                    <NavLink to="/manager/return-requests" className={linkClass}>
                      Возвраты (завснар)
                    </NavLink>
                    <NavLink to="/manager/rentals" className={linkClass}>
                      Аренды
                    </NavLink>
                  </>
                )}
                {me.role === "admin" && (
                  <NavLink to="/admin/users" className={linkClass}>
                    Пользователи
                  </NavLink>
                )}
              </>
            ) : null}
          </nav>
          <div className="flex items-center gap-3 text-sm">
            {me ? (
              <>
                <span className="text-muted-foreground max-w-[220px] truncate" title={me.email}>
                  {me.full_name} · {me.role}
                </span>
                <Button variant="outline" size="sm" type="button" onClick={() => void onLogout()}>
                  Выйти
                </Button>
              </>
            ) : (
              <Button asChild size="sm">
                <NavLink to="/login">Войти</NavLink>
              </Button>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
