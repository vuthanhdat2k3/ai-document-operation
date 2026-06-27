'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  FileText,
  Search,
  MessageSquare,
  FileBarChart,
  Bot,
  User as UserIcon,
  Shield,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/lib/store';
import { useAuthContext } from '@/components/auth/AuthProvider';

const mainNavItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/chat', label: 'Chat', icon: MessageSquare },
  { href: '/reports', label: 'Reports', icon: FileBarChart },
  { href: '/agent', label: 'Agent', icon: Bot },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useAppStore();
  const { user } = useAuthContext();

  const isActive = (href: string) =>
    pathname === href || (href !== '/' && pathname.startsWith(href));

  return (
    <aside
      className={cn(
        'flex flex-col bg-card/50 backdrop-blur-sm transition-all duration-300 border-r border-border/40',
        sidebarCollapsed ? 'w-16' : 'w-60',
      )}
      aria-label="Main navigation"
    >
      {/* Logo / Brand */}
      <div className="flex h-14 items-center justify-between px-3">
        {!sidebarCollapsed && (
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-primary">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="text-sm font-semibold tracking-tight">DocOps</span>
          </Link>
        )}
        <button
          onClick={toggleSidebar}
          className="rounded-lg p-1.5 text-muted-foreground/40 transition-colors hover:bg-accent hover:text-foreground"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!sidebarCollapsed}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2" role="navigation">
        {mainNavItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
                active
                  ? 'bg-primary/[0.06] text-foreground font-semibold'
                  : 'text-muted-foreground/60 hover:bg-accent/40 hover:text-foreground',
                sidebarCollapsed && 'justify-center px-2',
              )}
              aria-current={active ? 'page' : undefined}
            >
              {active && (
                <span className="absolute left-0.5 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-sidebar-active" />
              )}
              <Icon className={cn('h-4 w-4 shrink-0', active ? 'text-primary' : '')} />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </Link>
          );
        })}

        {/* Admin section */}
        {user?.role === 'admin' && !sidebarCollapsed && (
          <div className="pt-4">
            <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/40">
              Admin
            </p>
            <Link
              href="/admin"
              className={cn(
                'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
                isActive('/admin')
                  ? 'bg-primary/[0.06] text-foreground'
                  : 'text-muted-foreground/60 hover:bg-accent/40 hover:text-foreground',
              )}
              aria-current={isActive('/admin') ? 'page' : undefined}
            >
              {isActive('/admin') && (
                <span className="absolute left-0.5 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-sidebar-active" />
              )}
              <Shield className={cn('h-4 w-4 shrink-0', isActive('/admin') ? 'text-primary' : '')} />
              <span>Admin Panel</span>
            </Link>
          </div>
        )}
      </nav>

      {/* Bottom: Profile */}
      <div className="border-t border-border/40 p-2">
        <Link
          href="/profile"
          className={cn(
            'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
            isActive('/profile')
              ? 'bg-primary/[0.06] text-foreground'
              : 'text-muted-foreground/60 hover:bg-accent/40 hover:text-foreground',
            sidebarCollapsed && 'justify-center px-2',
          )}
          aria-current={isActive('/profile') ? 'page' : undefined}
        >
          {isActive('/profile') && (
            <span className="absolute left-0.5 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-sidebar-active" />
          )}
          <UserIcon className={cn('h-4 w-4 shrink-0', isActive('/profile') ? 'text-primary' : '')} />
          {!sidebarCollapsed && <span>Profile</span>}
        </Link>
      </div>
    </aside>
  );
}
