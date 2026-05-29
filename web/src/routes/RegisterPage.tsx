import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/http";
import { register, requestRegistrationCode, verifyRegistrationCode, type RegisterPayload } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const MIN_PASSWORD_LEN = 8;
const CODE_LEN = 6;

type RegistrationStep = "details" | "code";

export function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo =
    (location.state as { from?: string } | undefined)?.from && (location.state as { from?: string }).from !== "/register"
      ? (location.state as { from: string }).from
      : undefined;
  const loginState = redirectTo ? { from: redirectTo } : undefined;

  const [step, setStep] = useState<RegistrationStep>("details");
  const [pendingPayload, setPendingPayload] = useState<RegisterPayload | null>(null);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const passwordTooShort = password.length > 0 && password.length < MIN_PASSWORD_LEN;
  const passwordsDontMatch = confirmPassword.length > 0 && password !== confirmPassword;
  const normalizedEmail = email.trim().toLowerCase();
  const normalizedCode = code.trim();

  const isDetailsSubmitDisabled =
    busy ||
    normalizedEmail.length === 0 ||
    fullName.trim().length === 0 ||
    phone.trim().length === 0 ||
    password.length < MIN_PASSWORD_LEN ||
    password !== confirmPassword;

  const isCodeSubmitDisabled = busy || pendingPayload === null || normalizedCode.length !== CODE_LEN;

  function apiErrorMessage(err: unknown, fallback: string): string {
    if (err instanceof ApiError) {
      return err.message;
    }
    return fallback;
  }

  async function onDetailsSubmit(e: FormEvent) {
    e.preventDefault();
    if (isDetailsSubmitDisabled) return;

    const payload: RegisterPayload = {
      email: normalizedEmail,
      full_name: fullName.trim(),
      phone: phone.trim(),
      document: null,
      password,
    };

    setError(null);
    setBusy(true);

    try {
      await requestRegistrationCode(payload.email);
      setPendingPayload(payload);
      setCode("");
      setStep("code");
    } catch (err) {
      setError(apiErrorMessage(err, "Не удалось отправить код подтверждения"));
    } finally {
      setBusy(false);
    }
  }

  async function onCodeSubmit(e: FormEvent) {
    e.preventDefault();
    if (isCodeSubmitDisabled || pendingPayload === null) return;

    setError(null);
    setBusy(true);

    try {
      await verifyRegistrationCode(pendingPayload.email, normalizedCode);
      await register(pendingPayload);
      navigate("/login", { replace: true, state: loginState });
    } catch (err) {
      setError(apiErrorMessage(err, "Не удалось завершить регистрацию"));
    } finally {
      setBusy(false);
    }
  }

  function backToDetails() {
    if (busy) return;
    setStep("details");
    setError(null);
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Регистрация</CardTitle>
          <CardDescription>
            {step === "details"
              ? "Заполните данные, и мы отправим код подтверждения на email."
              : `Введите код, отправленный на ${pendingPayload?.email ?? normalizedEmail}.`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {step === "details" ? (
            <form onSubmit={(e) => void onDetailsSubmit(e)} className="space-y-4" noValidate>
              <div className="space-y-2">
                <Label htmlFor="reg-email">Email</Label>
                <Input id="reg-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-name">ФИО</Label>
                <Input id="reg-name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-phone">Телефон</Label>
                <Input id="reg-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+79991234567" required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-password">Пароль</Label>
                <Input
                  id="reg-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={MIN_PASSWORD_LEN}
                  required
                />
                {passwordTooShort ? <p className="text-xs text-muted-foreground">Минимум {MIN_PASSWORD_LEN} символов.</p> : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-confirm-password">Подтверждение пароля</Label>
                <Input
                  id="reg-confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
                {passwordsDontMatch ? <p className="text-xs text-destructive">Пароли не совпадают.</p> : null}
              </div>
              {error ? <p className="text-destructive text-sm">{error}</p> : null}
              <Button type="submit" className="w-full" disabled={isDetailsSubmitDisabled}>
                {busy ? "Отправляем код…" : "Получить код"}
              </Button>
            </form>
          ) : (
            <form onSubmit={(e) => void onCodeSubmit(e)} className="space-y-4" noValidate>
              <div className="space-y-2">
                <Label htmlFor="reg-code">Код подтверждения</Label>
                <Input
                  id="reg-code"
                  inputMode="numeric"
                  maxLength={CODE_LEN}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, CODE_LEN))}
                  placeholder="000000"
                  required
                />
                <p className="text-xs text-muted-foreground">Код состоит из {CODE_LEN} цифр и действует ограниченное время.</p>
              </div>
              {error ? <p className="text-destructive text-sm">{error}</p> : null}
              <div className="flex flex-col gap-2">
                <Button type="submit" className="w-full" disabled={isCodeSubmitDisabled}>
                  {busy ? "Проверяем код…" : "Завершить регистрацию"}
                </Button>
                <Button type="button" variant="ghost" className="w-full" onClick={backToDetails} disabled={busy}>
                  Изменить данные
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
      <p className="text-center text-xs text-muted-foreground">
        Уже есть аккаунт?{" "}
        <Link className="underline-offset-4 hover:underline" to="/login" state={loginState}>
          Войти
        </Link>
      </p>
    </div>
  );
}
