import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listAdminUsers } from "@/api/admin";
import { RequireAuth, RequireRole } from "@/components/auth/Guards";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export function AdminUsersPage() {
  return (
    <RequireAuth>
      <RequireRole allow={["admin"]}>
        <AdminUsersInner />
      </RequireRole>
    </RequireAuth>
  );
}

function AdminUsersInner() {
  const [name, setName] = useState("");
  const [applied, setApplied] = useState<string | undefined>(undefined);

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["admin-users", applied],
    queryFn: () => listAdminUsers(applied),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Пользователи</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Список из API. Назначение ролей через PATCH пока только из админских эндпоинтов вне этого экрана.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Поиск</CardTitle>
          <CardDescription>Фильтр по ФИО (ilike на сервере).</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="space-y-2">
            <Label htmlFor="an">Имя</Label>
            <Input id="an" value={name} onChange={(e) => setName(e.target.value)} placeholder="Фрагмент ФИО" />
          </div>
          <Button type="button" onClick={() => setApplied(name.trim() || undefined)}>
            Применить
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Результат</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">id</th>
                  <th className="py-2 pr-3 font-medium">email</th>
                  <th className="py-2 pr-3 font-medium">ФИО</th>
                  <th className="py-2 pr-3 font-medium">телефон</th>
                  <th className="py-2 pr-3 font-medium">роль</th>
                  <th className="py-2 font-medium">активен</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-border/60">
                    <td className="py-2 pr-3">{u.id}</td>
                    <td className="py-2 pr-3">{u.email}</td>
                    <td className="py-2 pr-3">{u.full_name}</td>
                    <td className="py-2 pr-3">{u.phone}</td>
                    <td className="py-2 pr-3">{u.role}</td>
                    <td className="py-2">{u.is_active ? "да" : "нет"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!isLoading && users.length === 0 ? (
            <p className="text-muted-foreground mt-4 text-sm">Пусто.</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
