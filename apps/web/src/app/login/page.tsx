"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { ThemeMenu } from "@/components/ThemeMenu";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import { useLogin, useSession } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const session = useSession();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (session.data) router.replace("/");
  }, [session.data, router]);

  return (
    <main className="relative flex flex-1 items-center justify-center p-6">
      <div className="absolute right-4 top-4">
        <ThemeMenu />
      </div>
      <div className="flex w-full max-w-sm flex-col items-center gap-6">
        <Logo className="scale-110" />
        <Card className="w-full">
          <CardContent>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                login.mutate({ email, password });
              }}
              className="flex flex-col gap-4"
            >
              <div>
                <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
                <p className="mt-1 text-[0.8125rem] text-muted-foreground">
                  Your applications, preparation and practice in one place.
                </p>
              </div>

              <Field label="Email">
                {(p) => (
                  <Input
                    type="email"
                    autoComplete="username"
                    required
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    {...p}
                  />
                )}
              </Field>

              <Field label="Password">
                {(p) => (
                  <Input
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    {...p}
                  />
                )}
              </Field>

              <p role="alert" className="min-h-5 text-sm text-danger-text">
                {login.error?.message}
              </p>

              <Button type="submit" variant="primary" loading={login.isPending} className="w-full">
                {login.isPending ? "Signing in" : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
