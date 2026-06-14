# Dashboard Component Patterns

## Extended Card Variants

### Metric Card with Sparkline

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

function MetricCard({ title, value, data, dataKey }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <div className="h-[60px] mt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary) / 0.1)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
```

### Progress Card

```tsx
function ProgressCard({ title, current, target, color = "primary" }: ProgressCardProps) {
  const percentage = Math.round((current / target) * 100);
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-bold">{current.toLocaleString()}</span>
          <span className="text-sm text-muted-foreground">/ {target.toLocaleString()}</span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div 
            className={cn("h-full rounded-full", `bg-${color}`)}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground text-right">{percentage}%</p>
      </CardContent>
    </Card>
  );
}
```

## Table Patterns

### Sortable Table

```tsx
"use client";

import { useState } from "react";
import { ArrowUpDown } from "lucide-react";

function SortableTable({ data, columns }: TableProps) {
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);

  const sortedData = useMemo(() => {
    if (!sortConfig) return data;
    return [...data].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      if (aVal < bVal) return sortConfig.direction === "asc" ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  const handleSort = (key: string) => {
    setSortConfig((current) => ({
      key,
      direction: current?.key === key && current.direction === "asc" ? "desc" : "asc",
    }));
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((col) => (
            <TableHead key={col.key}>
              <button 
                className="flex items-center gap-1 hover:text-foreground"
                onClick={() => handleSort(col.key)}
              >
                {col.label}
                <ArrowUpDown className="h-3 w-3" />
              </button>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedData.map((row, i) => (
          <TableRow key={i}>
            {columns.map((col) => (
              <TableCell key={col.key}>{row[col.key]}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

### Searchable Filter Table

```tsx
function FilterableTable({ data, columns }: TableProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredData = useMemo(() => {
    return data.filter((row) => {
      const matchesSearch = Object.values(row).some((val) =>
        String(val).toLowerCase().includes(search.toLowerCase())
      );
      const matchesStatus = statusFilter === "all" || row.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [data, search, statusFilter]);

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <Input
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <Table>
        {/* ... table content */}
      </Table>
      
      <div className="text-sm text-muted-foreground">
        Showing {filteredData.length} of {data.length} results
      </div>
    </div>
  );
}
```

## Form Patterns

### Dashboard Settings Form

```tsx
function DashboardSettings() {
  const form = useForm<Settings>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      refreshInterval: 30,
      theme: "system",
      notifications: true,
    },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="refreshInterval"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Refresh Interval (seconds)</FormLabel>
              <FormControl>
                <Input type="number" {...field} />
              </FormControl>
              <FormDescription>
                How often to fetch new data. Set to 0 to disable auto-refresh.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="theme"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Theme</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="light">Light</SelectItem>
                  <SelectItem value="dark">Dark</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit">Save Settings</Button>
      </form>
    </Form>
  );
}
```

## Notification Patterns

### Toast Notifications

```tsx
import { toast } from "sonner";

function useDashboardActions() {
  const handleExport = async () => {
    try {
      const data = await exportData();
      toast.success("Export complete", {
        description: "Your data has been downloaded.",
      });
    } catch (error) {
      toast.error("Export failed", {
        description: "Please try again later.",
      });
    }
  };

  const handleRefresh = async () => {
    const toastId = toast.loading("Refreshing data...");
    try {
      await refreshData();
      toast.success("Data refreshed", { id: toastId });
    } catch (error) {
      toast.error("Refresh failed", { id: toastId });
    }
  };

  return { handleExport, handleRefresh };
}
```

### Live Status Banner

```tsx
function LiveStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdate(new Date());
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!isOnline) {
    return (
      <div className="bg-red-500 text-white px-4 py-2 text-sm flex items-center gap-2">
        <AlertCircle className="h-4 w-4" />
        <span>Connection lost. Retrying...</span>
      </div>
    );
  }

  return (
    <div className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 px-4 py-2 text-sm flex items-center gap-2">
      <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
      <span>Live • Updated {format(lastUpdate, "HH:mm:ss")}</span>
    </div>
  );
}
```
