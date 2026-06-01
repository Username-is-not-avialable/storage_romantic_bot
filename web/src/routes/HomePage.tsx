import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/auth/useMe";

export function HomePage() {
  const { data: me } = useMe();

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Склад туристского снаряжения</h1>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Каталог</CardTitle>
            <CardDescription>Свободные позиции и поиск по названию.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="secondary">
              <Link to="/catalog">Открыть каталог</Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{me ? "Личный кабинет" : "Вход"}</CardTitle>
            <CardDescription>
              {me ? "Активные аренды и статусы заявок." : "Авторизуйтесь, чтобы подавать заявки."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {me ? (
              <Button asChild>
                <Link to="/me">Мой склад</Link>
              </Button>
            ) : (
              <Button asChild>
                <Link to="/login">Войти</Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
