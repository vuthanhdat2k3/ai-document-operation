# Chart Configuration Examples

## Chart Library Selection

| Library | Best For | Size |
|---------|----------|------|
| Recharts | React apps, simple charts | ~45KB |
| Chart.js | Vanilla JS, lightweight | ~60KB |
| D3.js | Custom visualizations | ~230KB |
| Victory | React, animation-heavy | ~80KB |
| ECharts | Complex charts, large datasets | ~300KB |
| Nivo | Declarative, beautiful defaults | ~150KB |

## Recharts Patterns

### Line Chart with Area

```tsx
import {
  LineChart,
  Line,
  Area,
  AreaChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const data = [
  { month: "Jan", revenue: 4000, expenses: 2400 },
  { month: "Feb", revenue: 3000, expenses: 1398 },
  { month: "Mar", revenue: 9800, expenses: 2000 },
];

function RevenueChart() {
  return (
    <ResponsiveContainer width="100%" height={350}>
      <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="month" className="text-xs" />
        <YAxis className="text-xs" />
        <Tooltip 
          contentStyle={{ 
            backgroundColor: "hsl(var(--popover))", 
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
        />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke="hsl(var(--primary))"
          fillOpacity={1}
          fill="url(#colorRevenue)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

### Bar Chart with Multiple Series

```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

const data = [
  { name: "Mon", tasks: 4, completed: 3 },
  { name: "Tue", tasks: 6, completed: 5 },
  { name: "Wed", tasks: 8, completed: 7 },
  { name: "Thu", tasks: 5, completed: 4 },
  { name: "Fri", tasks: 7, completed: 6 },
];

function TasksChart() {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Bar dataKey="tasks" name="Total Tasks" fill="hsl(var(--muted))" />
        <Bar dataKey="completed" name="Completed" fill="hsl(var(--primary))" />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### Pie Chart with Custom Label

```tsx
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";

const data = [
  { name: "Desktop", value: 400 },
  { name: "Mobile", value: 300 },
  { name: "Tablet", value: 200 },
];

const COLORS = ["hsl(var(--primary))", "hsl(var(--secondary))", "hsl(var(--muted))"];

const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

function DeviceChart() {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={renderCustomLabel}
          outerRadius={100}
          dataKey="value"
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

## Chart.js Patterns

### Doughnut Chart

```tsx
import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";

ChartJS.register(ArcElement, Tooltip, Legend);

const data = {
  labels: ["Completed", "In Progress", "Pending"],
  datasets: [
    {
      data: [65, 25, 10],
      backgroundColor: [
        "rgba(34, 197, 94, 0.8)",
        "rgba(59, 130, 246, 0.8)",
        "rgba(234, 179, 8, 0.8)",
      ],
      borderWidth: 0,
    },
  ],
};

const options = {
  cutout: "70%",
  plugins: {
    legend: {
      position: "bottom" as const,
    },
  },
};

function TaskProgress() {
  return <Doughnut data={data} options={options} />;
}
```

### Mixed Chart (Line + Bar)

```tsx
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const data = {
  labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
  datasets: [
    {
      type: "bar" as const,
      label: "Sales",
      data: [120, 190, 170, 220, 280, 250],
      backgroundColor: "rgba(59, 130, 246, 0.5)",
      borderColor: "rgba(59, 130, 246, 1)",
      borderWidth: 1,
    },
    {
      type: "line" as const,
      label: "Trend",
      data: [120, 165, 170, 210, 250, 250],
      borderColor: "rgba(239, 68, 68, 1)",
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.4,
    },
  ],
};

function SalesWithTrend() {
  return <Bar data={data} options={{ responsive: true }} />;
}
```

## Chart Styling

### Dark Mode Colors

```tsx
const darkTheme = {
  grid: "rgba(255, 255, 255, 0.1)",
  text: "rgba(255, 255, 255, 0.7)",
  tooltip: {
    backgroundColor: "rgba(24, 24, 27, 0.95)",
    borderColor: "rgba(255, 255, 255, 0.1)",
  },
};

const lightTheme = {
  grid: "rgba(0, 0, 0, 0.1)",
  text: "rgba(0, 0, 0, 0.7)",
  tooltip: {
    backgroundColor: "rgba(255, 255, 255, 0.95)",
    borderColor: "rgba(0, 0, 0, 0.1)",
  },
};
```

### Responsive Chart Container

```tsx
function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full">
          {children}
        </div>
      </CardContent>
    </Card>
  );
}
```

## Chart Hooks

### useChartDimensions

```tsx
function useChartDimensions(containerRef: RefObject<HTMLDivElement>) {
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [containerRef]);

  return dimensions;
}
```

### useChartColors

```tsx
function useChartColors() {
  const { theme } = useTheme();
  
  return useMemo(() => ({
    primary: theme === "dark" ? "hsl(217, 91%, 60%)" : "hsl(221, 83%, 53%)",
    secondary: theme === "dark" ? "hsl(215, 20%, 65%)" : "hsl(215, 25%, 35%)",
    success: theme === "dark" ? "hsl(142, 71%, 45%)" : "hsl(142, 76%, 36%)",
    danger: theme === "dark" ? "hsl(0, 84%, 60%)" : "hsl(0, 84%, 60%)",
  }), [theme]);
}
```
