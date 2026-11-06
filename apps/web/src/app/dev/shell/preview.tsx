"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState, useSyncExternalStore } from "react";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const FAKE_SESSION = { user: { id: 0, email: "preview@example.com" }, csrf_token: "preview" };

const noopSubscribe = () => () => undefined;

/** Renders nothing during prerender (server snapshot is false), then the real preview in the browser. */
export function ShellPreview() {
  const inBrowser = useSyncExternalStore(noopSubscribe, () => true, () => false);
  return inBrowser ? <Preview /> : null;
}

function Preview() {
  const queryClient = useQueryClient();
  // Development only: a fake signed-in user in the session cache. Browser-only (see ShellPreview)
  // because the cache reads the clock, which must not happen while Next prerenders.
  useState(() => queryClient.setQueryData(["session"], FAKE_SESSION));
  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Today</h1>
          <p className="text-sm text-muted-foreground">Sample content inside the new shell.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {["Active applications", "Interviews this week", "Reviews due", "Tasks to check"].map((label, i) => (
            <Card key={label}>
              <CardHeader>
                <CardDescription>{label}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold tabular">{[12, 3, 18, 1][i]}</p>
              </CardContent>
            </Card>
          ))}
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Next best actions</CardTitle>
            <CardDescription>Chosen by rules, not by a model</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span>Follow up with Acme (applied 7 days ago)</span>
              <Badge tone="warning">Due today</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>Review 18 cards</span>
              <Badge tone="accent">About 9 min</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
