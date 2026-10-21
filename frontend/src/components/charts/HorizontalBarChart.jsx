import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltip, Legend, axisProps } from "./chartKit.jsx";

/**
 * Horizontal bars, one per category. Each row may carry its own `color` and `group`
 * (e.g. "remaining" vs "deducted"); a legend lists the groups when there are >= 2.
 * rows: [{ label, value, color, group }]
 */
export default function HorizontalBarChart({
  rows, valueFormat = (v) => v, groups, reference, height, labelWidth = 190, integer = false,
}) {
  const h = height ?? Math.max(120, rows.length * 36 + 40 + (reference ? 18 : 0));
  return (
    <div>
      {groups && groups.length > 1 && <Legend items={groups.map((g) => ({ ...g, swatch: true }))} />}
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={rows} layout="vertical" margin={{ top: reference ? 22 : 4, right: 64, bottom: 4, left: 8 }} barCategoryGap={8}>
          <CartesianGrid stroke="var(--line)" horizontal={false} />
          <XAxis type="number" tickFormatter={valueFormat} allowDecimals={!integer} {...axisProps} />
          <YAxis type="category" dataKey="label" width={labelWidth} {...axisProps} tick={{ fill: "var(--ink-2)", fontSize: 12 }} />
          <Tooltip content={<ChartTooltip valueFormatter={(v) => valueFormat(v)} />} cursor={{ fill: "var(--surface-2)" }} />
          {reference && (
            <ReferenceLine x={reference.value} stroke="var(--critical)" strokeWidth={1.5}
                           label={{ value: reference.label, position: "top", fill: "var(--ink-2)", fontSize: 11 }} />
          )}
          <Bar dataKey="value" name="Value" maxBarSize={24} minPointSize={2} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {rows.map((r, i) => <Cell key={i} fill={r.color ?? "var(--series-1)"} />)}
            <LabelList dataKey="value" position="right" formatter={valueFormat}
                       style={{ fill: "var(--ink)", fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
