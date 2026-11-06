import {
  BarChart3,
  BookOpen,
  Briefcase,
  CalendarCheck,
  ClipboardCheck,
  Code2,
  GraduationCap,
  Compass,
  ListChecks,
  type LucideIcon,
  MessageSquareText,
  Mic,
  Network,
  Sparkles,
  Star,
  UserRound,
  Wallet,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };
export type NavGroup = { label: string; items: NavItem[] };

/** The one navigation map (docs/phase-7/09-product-spec.md section 4). Icons come only from here. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/", label: "Today", icon: CalendarCheck },
      { href: "/jobs", label: "Jobs", icon: Briefcase },
      { href: "/discover", label: "Discover", icon: Compass },
      { href: "/apply", label: "Apply list", icon: ClipboardCheck },
    ],
  },
  {
    label: "Prepare",
    items: [
      { href: "/learn", label: "Learn", icon: GraduationCap },
      { href: "/prep", label: "Prep", icon: BookOpen },
      { href: "/practice", label: "Practice", icon: Code2 },
      { href: "/mock", label: "Mock", icon: Mic },
      { href: "/ask", label: "Ask", icon: MessageSquareText },
      { href: "/stories", label: "Stories", icon: Star },
    ],
  },
  {
    label: "Analyse",
    items: [
      { href: "/insights", label: "Insights", icon: BarChart3 },
      { href: "/offers", label: "Offers", icon: Wallet },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/profile", label: "Profile", icon: UserRound },
      { href: "/architecture", label: "How it works", icon: Network },
      { href: "/tasks", label: "Tasks", icon: ListChecks },
    ],
  },
];

export const BRAND_ICON = Sparkles;

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Title for the top bar: the label of the nav item that matches the current path. */
export function titleFor(pathname: string): string {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) if (isActive(pathname, item.href)) return item.label;
  }
  return "CareerPilot";
}
