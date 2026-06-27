'use client';

import { useRouter } from 'next/navigation';
import { useAuthContext } from '@/components/auth/AuthProvider';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LogOut, Mail, Shield, Calendar } from 'lucide-react';
import { formatDate } from '@/lib/utils';

export default function ProfilePage() {
  const router = useRouter();
  const { user, logout } = useAuthContext();

  const handleLogout = () => {
    logout();
    router.replace('/login');
  };

  if (!user) return null;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Profile</h2>
        <p className="mt-1 text-sm text-muted-foreground/70">Manage your account settings.</p>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/[0.08] ring-1 ring-primary/[0.1] text-lg font-bold text-primary">
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div>
              <CardTitle className="text-base">{user.full_name}</CardTitle>
              <CardDescription className="text-xs">{user.email}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-3 rounded-xl bg-secondary/30 p-3.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/[0.06]">
                <Mail className="h-4 w-4 text-primary/70" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">Email</p>
                <p className="text-sm font-medium truncate">{user.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-xl bg-secondary/30 p-3.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/[0.06]">
                <Shield className="h-4 w-4 text-primary/70" />
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">Role</p>
                <Badge variant={user.role === 'admin' ? 'default' : 'secondary'} className="mt-0.5 text-[10px] px-2">
                  {user.role}
                </Badge>
              </div>
            </div>
            {user.created_at && (
              <div className="flex items-center gap-3 rounded-xl bg-secondary/30 p-3.5 sm:col-span-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/[0.06]">
                  <Calendar className="h-4 w-4 text-primary/70" />
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">Member since</p>
                  <p className="text-sm font-medium">{formatDate(user.created_at)}</p>
                </div>
              </div>
            )}
          </div>

          <div className="pt-2">
            <Button variant="destructive" onClick={handleLogout} className="w-full sm:w-auto rounded-lg text-xs h-8">
              <LogOut className="mr-1.5 h-3.5 w-3.5" />
              Sign out
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
