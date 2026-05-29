import { useMemo, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { login, fetchMe } from "@/api/auth";
import { ApiError } from "@/api/http";
import { ME_QUERY_KEY } from "@/auth/useMe";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useMe } from "@/auth/useMe";

const MIN_PASSWORD_LEN = 8;

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const { data: me, isPending } = useMe();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const redirectTo =
    (location.state as { from?: string } | undefined)?.from && (location.state as { from?: string }).from !== "/login"
      ? (location.state as { from: string }).from
      : "/me";
  const registerState = redirectTo !== "/me" ? { from: redirectTo } : undefined;

  const emailNormalized = useMemo(() => email.trim().toLowerCase(), [email]);
  const passwordTooShort = password.length > 0 && password.length < MIN_PASSWORD_LEN;
  const isSubmitDisabled = busy || emailNormalized.length === 0 || password.length < MIN_PASSWORD_LEN;

  if (!isPending && me) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-6">
        <p className="text-sm text-muted-foreground">Вы уже вошли.</p>
        <Button asChild>
          <Link to={redirectTo}>Продолжить</Link>
        </Button>
      </div>
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (isSubmitDisabled) {
      return;
    }

    setError(null);
    setBusy(true);
    try {
      await login(emailNormalized, password);
      const user = await fetchMe();
      qc.setQueryData(ME_QUERY_KEY, user);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "Неверный email или пароль" : err.message);
      } else {
        setError("Не удалось выполнить вход");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Вход</CardTitle>
          <CardDescription>Введите email и пароль учетной записи клуба.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void onSubmit(e)} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={MIN_PASSWORD_LEN}
                required
              />
              {passwordTooShort ? (
                <p className="text-xs text-muted-foreground">Минимум {MIN_PASSWORD_LEN} символов.</p>
              ) : null}
            </div>
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            <Button type="submit" className="w-full" disabled={isSubmitDisabled}>
              {busy ? "Вход…" : "Войти"}
            </Button>
          </form>
        </CardContent>
      </Card>
      <div className="space-y-2 text-center text-xs text-muted-foreground">
        <p>
          Нет аккаунта?{" "}
          <Link className="underline-offset-4 hover:underline" to="/register" state={registerState}>
            Зарегистрироваться
          </Link>
        </p>
        <p>
          <Link className="underline-offset-4 hover:underline" to="/">
            На главную
          </Link>
        </p>
      </div>
    </div>
  );
}
