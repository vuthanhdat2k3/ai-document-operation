'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Moon, Sun, Bell, User as UserIcon, LogOut, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuthContext } from '@/components/auth/AuthProvider';

export function Header() {
  const router = useRouter();
  const { user, logout, isAuthenticated } = useAuthContext();
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem('theme') as 'light' | 'dark' | null;
    if (saved) {
      setTheme(saved);
      document.documentElement.classList.toggle('dark', saved === 'dark');
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.documentElement.classList.toggle('dark', newTheme === 'dark');
  };

  const handleLogout = () => {
    logout();
    setMenuOpen(false);
    router.push('/login');
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-card/95 px-6 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-semibold">AI Document Operations</h1>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="h-5 w-5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? (
            <Moon className="h-5 w-5" />
          ) : (
            <Sun className="h-5 w-5" />
          )}
        </Button>

        {isAuthenticated && user ? (
          <div className="relative ml-2" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2 rounded-full p-1 hover:bg-accent transition-colors"
              aria-label="User menu"
              aria-expanded={menuOpen}
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
                {user.full_name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-md border bg-card shadow-lg animate-in fade-in slide-in-from-top-2">
                <div className="border-b px-4 py-3">
                  <p className="text-sm font-medium">{user.full_name}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                  <span className="mt-1 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    {user.role}
                  </span>
                </div>
                <div className="p-1">
                  <Link
                    href="/profile"
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent transition-colors"
                    onClick={() => setMenuOpen(false)}
                  >
                    <UserIcon className="h-4 w-4" />
                    Profile
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={() => router.push('/login')}>
            Sign in
          </Button>
        )}
      </div>
    </header>
  );
}
