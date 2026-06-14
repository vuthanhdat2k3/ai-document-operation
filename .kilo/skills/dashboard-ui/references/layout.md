# Dashboard Layout Systems

## Core Layout Patterns

### 1. Collapsible Sidebar

```tsx
"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, LayoutDashboard, Users, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
  { icon: Users, label: "Users", href: "/users" },
  { icon: Settings, label: "Settings", href: "/settings" },
];

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen">
      <aside
        className={cn(
          "flex flex-col border-r bg-muted/40 transition-all duration-300",
          collapsed ? "w-[68px]" : "w-64"
        )}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b">
          {!collapsed && <span className="font-semibold">Acme</span>}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md hover:bg-accent"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
        
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm",
                "hover:bg-accent hover:text-accent-foreground",
                "transition-colors"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </a>
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b flex items-center px-6">
          <h1 className="text-lg font-semibold">Dashboard</h1>
        </header>
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
```

### 2. Grid Dashboard

```tsx
function DashboardGrid() {
  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Revenue" value="$45,231" change={12} />
        <StatCard title="Subscriptions" value="+2,350" change={18} />
        <StatCard title="Active Now" value="+573" change={-3} />
        <StatCard title="Bounce Rate" value="21.3%" change={-5} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Revenue Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <RevenueChart />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Top Pages</CardTitle>
          </CardHeader>
          <CardContent>
            <TopPagesTable />
          </CardContent>
        </Card>
      </div>

      {/* Full Width Table */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Orders</CardTitle>
        </CardHeader>
        <CardContent>
          <OrdersTable />
        </CardContent>
      </Card>
    </div>
  );
}
```

### 3. Split Layout (Sidebar + Content)

```tsx
function SplitDashboard() {
  return (
    <div className="flex h-screen bg-background">
      {/* Left Panel - Filters */}
      <aside className="w-80 border-r p-6 overflow-auto">
        <h2 className="font-semibold mb-4">Filters</h2>
        <FilterPanel />
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 border-b flex items-center justify-between px-6">
          <h1 className="font-semibold">Results</h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">Export</Button>
            <Button size="sm">Add New</Button>
          </div>
        </header>
        
        <div className="flex-1 overflow-auto p-6">
          <DataTable />
        </div>
        
        <footer className="border-t px-6 py-3 flex items-center justify-between text-sm text-muted-foreground">
          <span>Showing 1-10 of 100 results</span>
          <Pagination />
        </footer>
      </main>
    </div>
  );
}
```

## Responsive Breakpoints

### Mobile-First Approach

```tsx
// Grid responsive columns
<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">

// Sidebar collapse on mobile
<aside className="
  fixed inset-y-0 left-0 z-50 w-64 bg-background border-r
  md:relative md:translate-x-0
  data-[state=open]:translate-x-0 data-[state=closed]:-translate-x-full
  transition-transform
">

// Header responsive
<header className="
  h-14 px-4 
  sm:h-16 sm:px-6
  lg:h-16 lg:px-8
">

// Content padding
<main className="
  p-4
  sm:p-6
  lg:p-8
  max-w-[1400px] mx-auto
">
```

### Mobile Navigation

```tsx
function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={() => setOpen(true)}
      >
        <Menu className="h-5 w-5" />
      </Button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-72">
          <nav className="space-y-2">
            {navItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="block px-3 py-2 rounded-md hover:bg-accent"
                onClick={() => setOpen(false)}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </SheetContent>
      </Sheet>
    </>
  );
}
```

## Spacing System

### Dashboard Spacing Scale

```tsx
const spacing = {
  // Component gaps
  cardGap: "gap-4",           // 16px
  sectionGap: "gap-6",        // 24px
  pageGap: "gap-8",           // 32px
  
  // Component padding
  cardPadding: "p-4 sm:p-6",  // 16-24px
  sectionPadding: "p-6 lg:p-8", // 24-32px
  pagePadding: "p-4 sm:p-6 lg:p-8",
  
  // Margins
  sectionMargin: "mb-6 lg:mb-8",
  pageMargin: "max-w-[1400px] mx-auto",
};
```

### Content Width Rules

```tsx
// Full width dashboard content
<main className="flex-1 p-6 max-w-[1400px] mx-auto">

// Narrow content (settings, forms)
<main className="flex-1 p-6 max-w-2xl mx-auto">

// Wide content (tables, charts)
<main className="flex-1 p-6 max-w-[1600px] mx-auto">
```

## Header Patterns

### Sticky Header with Actions

```tsx
function DashboardHeader({ title, actions }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 h-14 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-full items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-4">
          <MobileNav />
          <h1 className="font-semibold text-lg">{title}</h1>
        </div>
        
        <div className="flex items-center gap-2">
          {actions}
          <Separator orientation="vertical" className="h-6 mx-2 hidden sm:block" />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
```

### Breadcrumb Header

```tsx
function BreadcrumbHeader() {
  return (
    <header className="border-b">
      <div className="flex h-14 items-center px-4 sm:px-6">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/dashboard">Dashboard</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbLink href="/dashboard/analytics">Analytics</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>Overview</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>
    </header>
  );
}
```

## Footer Patterns

### Dashboard Footer

```tsx
function DashboardFooter() {
  return (
    <footer className="border-t bg-muted/40">
      <div className="flex h-12 items-center justify-between px-4 sm:px-6 text-sm text-muted-foreground">
        <span>© 2024 Acme Inc.</span>
        <div className="flex items-center gap-4">
          <a href="/docs" className="hover:text-foreground">Docs</a>
          <a href="/support" className="hover:text-foreground">Support</a>
          <a href="/status" className="flex items-center gap-1">
            <div className="h-2 w-2 rounded-full bg-emerald-500" />
            All systems operational
          </a>
        </div>
      </div>
    </footer>
  );
}
```

## Z-Index Scale

```tsx
const zIndex = {
  base: 0,
  dropdown: 50,
  sticky: 100,
  header: 200,
  sidebar: 250,
  modal: 300,
  popover: 400,
  toast: 500,
};
```

## Animation Patterns

### Page Transitions

```tsx
"use client";

import { motion } from "framer-motion";

function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
```

### Staggered List

```tsx
function StaggeredList({ items }: { items: string[] }) {
  return (
    <motion.ul className="space-y-2">
      {items.map((item, i) => (
        <motion.li
          key={item}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
        >
          {item}
        </motion.li>
      ))}
    </motion.ul>
  );
}
```
