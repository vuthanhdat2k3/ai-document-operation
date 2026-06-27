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

const bottomNavItems = [
  { href: '/profile', label: 'Profile', icon: UserIcon },
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
        'flex flex-col border-r bg-card transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-64',
      )}
      aria-label="Main navigation"
    >
      <div className="flex h-16 items-center justify-between border-b px-4">
        {!sidebarCollapsed && (
          <span className="text-lg font-semibold">DocOps AI</span>
        )}
        <button
          onClick={toggleSidebar}
          className="rounded-md p-1.5 hover:bg-accent"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!sidebarCollapsed}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-2" role="navigation">
        {mainNavItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive(item.href)
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                sidebarCollapsed && 'justify-center',
              )}
              aria-current={isActive(item.href) ? 'page' : undefined}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </Link>
          );
        })}

        {/* Admin section — only visible to admin users */}
        {user?.role === 'admin' && !sidebarCollapsed && (
          <div className="pt-4">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Admin
            </p>
            <Link
              href="/admin"
              className={cn(
                'mt-1 flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive('/admin')
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )}
              aria-current={isActive('/admin') ? 'page' : undefined}
            >
              <Shield className="h-5 w-5 shrink-0" />
              <span>Admin Panel</span>
            </Link>
          </div>
        )}
      </nav>

      {/* Bottom: Profile */}
      <div className="border-t p-2">
        <Link
          href="/profile"
          className={cn(
            'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
            isActive('/profile')
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
            sidebarCollapsed && 'justify-center',
          )}
          aria-current={isActive('/profile') ? 'page' : undefined}
        >
          <UserIcon className="h-5 w-5 shrink-0" />
          {!sidebarCollapsed && <span>Profile</span>}
        </Link>
      </div>
    </aside>
  );
}
