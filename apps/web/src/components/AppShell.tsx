"use client";

import { Dialog as DialogPrimitive } from "radix-ui";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { NAV_GROUPS, isActive, titleFor } from "@/components/nav";
import { ThemeMenu } from "@/components/ThemeMenu";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useProfile } from "@/features/profile/hooks";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useLogout, useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

function NavList({ pathname, collapsed, onNavigate }: { pathname: string; collapsed: boolean; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-1 flex-col gap-5 overflow-y-auto px-2 py-3">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="flex flex-col gap-0.5">
          <p className={cn("px-2 pb-1 text-xs font-medium text-muted-foreground", collapsed && "sr-only")}>
            {group.label}
          </p>
          {group.items.map((item) => {
            const active = isActive(pathname, item.href);
            const link = (
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-[var(--control-h)] items-center gap-2.5 rounded-md px-2 text-[length:var(--text-base)] font-medium",
                  "transition-colors duration-[var(--dur-fast)]",
                  collapsed && "justify-center",
                  active
                    ? "bg-accent-soft text-accent-text"
                    : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
                )}
              >
                <item.icon className="size-4 shrink-0" aria-hidden="true" />
                <span className={cn(collapsed && "sr-only")}>{item.label}</span>
              </Link>
            );
            return collapsed ? (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            ) : (
              <div key={item.href}>{link}</div>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

/** Signed-in frame: redirects to /login without a session; sidebar on desktop, drawer on phones. */
/** You, in the top bar: your name from account setup (your email until you have set it up). */
function UserChip({ email }: { email: string }) {
  const profile = useProfile();
  const name = profile.data?.full_name?.trim() || email;
  return (
    <Link
      href="/profile"
      className="mr-1 flex items-center gap-2 rounded-full py-1 pr-2 pl-1 transition-colors hover:bg-surface-hover"
    >
      <Avatar name={name} className="size-7 text-[0.6875rem]" />
      <span className="max-w-40 truncate text-[0.8125rem] text-muted-foreground max-sm:sr-only">{name}</span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const session = useSession();
  const logout = useLogout();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (session.isSuccess && session.data === null) router.replace("/login");
  }, [session.isSuccess, session.data, router]);

  if (session.isError) {
    return (
      <main className="flex flex-1 items-center justify-center p-6">
        <ErrorState
          title="The API is not reachable"
          description="Start the API and reload this page."
          onRetry={() => void session.refetch()}
        />
      </main>
    );
  }
  // Children render only once the session (and its CSRF token) is known.
  if (!session.data) {
    return (
      <main className="flex flex-1 flex-col gap-4 p-6" aria-busy="true">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </main>
    );
  }

  const email = session.data.user.email;
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex min-h-screen flex-1">
        {/* Desktop sidebar */}
        <aside
          className={cn(
            "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex",
            "transition-[width] duration-[var(--dur)]",
            collapsed ? "w-16" : "w-60",
          )}
        >
          <div className={cn("flex h-14 items-center px-4", collapsed && "justify-center px-0")}>
            <Link href="/" aria-label="CareerPilot home">
              <Logo variant={collapsed ? "compact" : "full"} />
            </Link>
          </div>
          <NavList pathname={pathname} collapsed={collapsed} />
          <div className="border-t border-sidebar-border p-2">
            <Button
              variant="ghost"
              size={collapsed ? "icon" : "md"}
              className={cn(!collapsed && "w-full justify-start")}
              onClick={() => setCollapsed((c) => !c)}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <PanelLeftOpen aria-hidden="true" /> : <PanelLeftClose aria-hidden="true" />}
              {collapsed ? null : "Collapse"}
            </Button>
          </div>
        </aside>

        {/* Mobile drawer */}
        <DialogPrimitive.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
          <DialogPrimitive.Portal>
            <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-overlay md:hidden" />
            <DialogPrimitive.Content
              aria-describedby={undefined}
              className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-sidebar-border bg-sidebar shadow-float md:hidden"
            >
              <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
              <div className="flex h-14 items-center px-4">
                <Logo />
              </div>
              <NavList pathname={pathname} collapsed={false} onNavigate={() => setDrawerOpen(false)} />
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        </DialogPrimitive.Root>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border-subtle bg-background/90 px-4 backdrop-blur md:px-6">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Open navigation"
              onClick={() => setDrawerOpen(true)}
            >
              <Menu aria-hidden="true" />
            </Button>
            <span className="text-sm font-medium text-muted-foreground">{titleFor(pathname)}</span>
            <div className="ml-auto flex items-center gap-1">
              <UserChip email={email} />
              <ThemeMenu />
              <Button variant="ghost" size="icon" aria-label="Sign out" onClick={() => logout.mutate()}>
                <LogOut aria-hidden="true" />
              </Button>
            </div>
          </header>
          <main key={pathname} className="page-enter mx-auto w-full max-w-6xl flex-1 p-4 md:p-6">
            {children}
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
