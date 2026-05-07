import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useMe } from "@/auth/useMe";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: me, isPending, isError } = useMe();
  const loc = useLocation();

  if (isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
        Проверка сессии…
      </div>
    );
  }

  if (isError || me == null) {
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }

  return children;
}

export function RequireRole({
  allow,
  children,
}: {
  allow: readonly ("member" | "manager" | "admin")[];
  children: ReactNode;
}) {
  const { data: me, isPending } = useMe();

  if (isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
        Загрузка…
      </div>
    );
  }

  if (me == null || !allow.includes(me.role)) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-6">
        <h1 className="text-lg font-semibold">Нет доступа</h1>
        <p className="text-sm text-muted-foreground">Недостаточно прав для этой страницы.</p>
        <Button asChild variant="outline">
          <a href="/">На главную</a>
        </Button>
      </div>
    );
  }

  return children;
}
