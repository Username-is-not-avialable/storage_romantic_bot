import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { requestVkLinkCode, type VkLinkCodeResponse } from "@/api/auth";
import { ApiError } from "@/api/http";
import { useMe } from "@/auth/useMe";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function formatExpiresAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function apiErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return err.message;
  }
  return "Не удалось получить код привязки VK";
}

export function VkLinkPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: me, isPending } = useMe();

  const [linkCode, setLinkCode] = useState<VkLinkCodeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [requestedForUserId, setRequestedForUserId] = useState<number | null>(null);

  const returnTo = `${location.pathname}${location.search}`;

  const loadCode = useCallback(async () => {
    if (!me || busy) return;

    setError(null);
    setBusy(true);
    try {
      const response = await requestVkLinkCode();
      setLinkCode(response);
      setRequestedForUserId(me.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [busy, me]);

  useEffect(() => {
    if (me && requestedForUserId !== me.id && !linkCode && !busy) {
      void loadCode();
    }
  }, [busy, linkCode, loadCode, me, requestedForUserId]);

  function goToLogin() {
    navigate("/login", { state: { from: returnTo } });
  }

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Привязка VK-бота</CardTitle>
          <CardDescription>
            Получите одноразовый код и отправьте его боту VK, чтобы связать ваш аккаунт сайта с VK.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isPending ? (
            <p className="text-sm text-muted-foreground">Проверяем авторизацию…</p>
          ) : me ? (
            <>
              {linkCode ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">Отправьте этот код боту VK одним сообщением:</p>
                  <div className="rounded-lg border bg-muted px-4 py-3 text-center font-mono text-2xl font-semibold tracking-widest">
                    {linkCode.code}
                  </div>
                  <p className="text-xs text-muted-foreground">Код действует до {formatExpiresAt(linkCode.expires_at)}.</p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">{busy ? "Получаем код…" : "Нажмите кнопку, чтобы получить код."}</p>
              )}
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <Button type="button" className="w-full" onClick={() => void loadCode()} disabled={busy}>
                {busy ? "Получаем код…" : linkCode ? "Получить новый код" : "Получить код"}
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                Чтобы получить код привязки, сначала войдите или зарегистрируйтесь на сайте.
              </p>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <Button type="button" className="w-full" onClick={goToLogin}>
                Получить код
              </Button>
            </>
          )}
        </CardContent>
      </Card>
      <p className="text-center text-xs text-muted-foreground">
        Уже получили код? Вернитесь в VK и отправьте его боту одним сообщением. <Link className="underline-offset-4 hover:underline" to="/me">Мой склад</Link>
      </p>
    </div>
  );
}
