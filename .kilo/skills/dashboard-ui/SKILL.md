---
name: dashboard-ui
description: Build beautiful, optimized dashboard UI with data visualization, layout patterns, and performance. Use when creating admin panels, analytics dashboards, data-heavy interfaces, monitoring systems, or any application requiring real-time data display and user interaction. Covers component patterns, chart integration, responsive design, and accessibility for data-dense interfaces.
---

# Dashboard UI

## Overview

Build production-ready dashboards with optimal data density, responsive layouts, and performant visualizations. This skill covers admin panels, analytics dashboards, monitoring systems, and data-heavy interfaces.

## Quick Start

### Stack Selection

| Use Case | Recommended Stack |
|----------|-------------------|
| React/Next.js SaaS | shadcn/ui + Tailwind + Recharts |
| Enterprise/Corporate | Carbon (IBM) or Fluent UI (Microsoft) |
| Material Design | Material UI v5 or MUI |
| Vue/Nuxt | Vuetify or PrimeVue |
| Lightweight | Bootstrap 5 + Chart.js |

### Install shadcn/ui Dashboard

```bash
npx shadcn@latest init
npx shadcn@latest add card chart table sidebar tabs badge avatar separator
```

## Layout Patterns

### 1. Sidebar + Content (Default)

```tsx
<div className="flex h-screen">
  <aside className="w-64 border-r bg-muted/40">
    <Sidebar />
  </aside>
  <main className="flex-1 overflow-auto">
    <Header />
    <div className="p-6">{children}</div>
  </main>
</div>
```

**Rules:**
- Sidebar: 240-280px width, collapsible to 64px icons-only
- Header: 56-64px height, sticky top
- Content: max-w-[1400px] mx-auto for readability

### 2. Top Nav + Content

```tsx
<div className="min-h-screen">
  <header className="h-16 border-b sticky top-0 bg-background z-40">
    <TopNav />
  </header>
  <main className="p-6 max-w-[1400px] mx-auto">{children}</main>
</div>
```

### 3. Grid Dashboard

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  <StatCard title="Revenue" value="$12,345" />
  <StatCard title="Users" value="1,234" />
  <StatCard title="Orders" value="567" />
  <StatCard title="Conversion" value="3.2%" />
</div>
```

## Component Patterns

### Stat Card

```tsx
function StatCard({ title, value, change, icon }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {change && (
          <p className={cn("text-xs", change > 0 ? "text-emerald-600" : "text-red-600")}>
            {change > 0 ? "+" : ""}{change}% from last month
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

### Data Table

```tsx
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Name</TableHead>
      <TableHead>Status</TableHead>
      <TableHead className="text-right">Amount</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {data.map((row) => (
      <TableRow key={row.id}>
        <TableCell>{row.name}</TableCell>
        <TableCell>
          <Badge variant={row.status === "active" ? "default" : "secondary"}>
            {row.status}
          </Badge>
        </TableCell>
        <TableCell className="text-right">${row.amount}</TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

### Chart Container

```tsx
<Card>
  <CardHeader>
    <CardTitle>Revenue Over Time</CardTitle>
    <CardDescription>Monthly revenue for 2024</CardDescription>
  </CardHeader>
  <CardContent>
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={revenueData}>
        <XAxis dataKey="month" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="revenue" stroke="hsl(var(--primary))" />
      </LineChart>
    </ResponsiveContainer>
  </CardContent>
</Card>
```

## Data Density Rules

### Visual Density: 7-9 (Cockpit Mode)

- **Font sizes:** `text-sm` for data, `text-base` for labels
- **Spacing:** `gap-3` to `gap-4`, `p-4` to `p-6`
- **No card backgrounds** for plain data rows; use `border-b` dividers
- **Monospace for numbers:** `font-mono` for all numeric values

### Metric Display

| Metric Type | Format | Example |
|-------------|--------|---------|
| Currency | Compact with $ | $12.3K, $1.2M |
| Percentage | 1 decimal | 3.2% |
| Large numbers | Abbreviated | 1.2M, 45K |
| Duration | HH:MM:SS | 02:34:56 |
| Date/Time | Relative | 2 hours ago |

### Chart Best Practices

1. **Max 5 series** per chart; more = use small multiples
2. **Never 3D charts** - always 2D flat
3. **Tooltip on hover**, not labels on every point
4. **Grid lines:** subtle `stroke-gray-200 dark:stroke-gray-800`
5. **Animation:** minimal, <300ms, ease-out only

## Real-Time Data

### Polling Pattern

```tsx
function usePolling<T>(url: string, interval = 5000) {
  const [data, setData] = useState<T | null>(null);
  
  useEffect(() => {
    const fetchData = async () => {
      const res = await fetch(url);
      setData(await res.json());
    };
    fetchData();
    const id = setInterval(fetchData, interval);
    return () => clearInterval(id);
  }, [url, interval]);
  
  return data;
}
```

### WebSocket Pattern

```tsx
function useWebSocket<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  
  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onmessage = (e) => setData(JSON.parse(e.data));
    return () => ws.close();
  }, [url]);
  
  return data;
}
```

## Dark Mode

Use Tailwind `dark:` variant consistently:

```tsx
<div className="bg-white dark:bg-zinc-950 text-gray-900 dark:text-gray-100">
  <Card className="bg-gray-50 dark:bg-zinc-900">
    <CardTitle className="text-gray-900 dark:text-gray-100">Metrics</CardTitle>
  </Card>
</div>
```

**Rules:**
- No pure `#000000` or `#ffffff` - use zinc-950/zinc-50
- Chart colors must work in both modes
- Test both modes before shipping

## Performance

### Virtual Scrolling (Large Lists)

```tsx
import { useVirtualizer } from "@tanstack/react-virtual";

function VirtualList({ items }: { items: Item[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
  });

  return (
    <div ref={parentRef} className="h-[500px] overflow-auto">
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((row) => (
          <div key={row.key} style={{ 
            position: "absolute", 
            top: row.start, 
            height: row.size 
          }}>
            {items[row.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Memoization

```tsx
// Memoize expensive calculations
const processedData = useMemo(() => {
  return rawData.map(transform).filter(filterFn);
}, [rawData]);

// Memoize chart components
const MemoizedChart = memo(Chart);
```

## Accessibility

1. **ARIA labels** on all interactive elements
2. **Keyboard navigation** for tables and forms
3. **Focus indicators** visible on all controls
4. **Color is not sole indicator** - add icons/text for status
5. **Screen reader announcements** for live data updates

```tsx
<Table aria-label="User analytics">
  <TableHeader>
    <TableRow>
      <TableHead scope="col">Name</TableHead>
    </TableRow>
  </TableHeader>
</Table>

<div role="status" aria-live="polite">
  {isLoading ? "Loading data..." : `${count} results found`}
</div>
```

## Forbidden Patterns

- ❌ Loading spinners in center of charts (use skeleton)
- ❌ Tables without sortable headers
- ❌ Charts without tooltips
- ❌ Pagination < 10 items
- ❌ Fixed layouts (always responsive)
- ❌ Auto-refresh without user control
- ❌ Console.log in production

## References

See `references/` for detailed guides:
- `components.md` - Extended component patterns
- `charts.md` - Chart configuration examples
- `layout.md` - Responsive layout systems
