import {
  CartesianGrid,
  ErrorBar,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTooltip, Legend, axisProps, gridProps } from "./chartKit.jsx";

/**
 * One or more measured series (mean ± 1 sd error bars, solid line, markers) with
 * optional theory curves (same hue, dashed, no markers).
 *
 * series: [{ key, name, color, theoryKey?, errKey? }]
 * rows:   [{ x, [key]: mean, [errKey]: std, [theoryKey]: value }]
 */
export default function MeasuredVsTheoryChart({
  rows,
  series,
  xLabel,
  yLabel,
  xFormat = (v) => v,
  yFormat = (v) => v,
  xScale = "linear",
  yScale = "linear",
  yDomain = [0, "auto"],
  yTicks,
  xTicks,
  reference,
  height = 300,
}) {
  const legendItems = series.flatMap((s) => [
    { name: `${s.name} (measured)`, color: s.color },
    ...(s.theoryKey ? [{ name: `${s.name} (theory)`, color: s.color, dashed: true }] : []),
  ]);
  if (reference) legendItems.push({ name: reference.label, color: "var(--critical)", noMarker: true });

  return (
    <div>
      <Legend items={legendItems} />
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 28, left: 8 }}>
          <CartesianGrid {...gridProps} />
          <XAxis
            dataKey="x"
            type="number"
            scale={xScale}
            domain={["dataMin", "dataMax"]}
            ticks={xTicks ?? rows.map((r) => r.x)}
            tickFormatter={xFormat}
            {...axisProps}
            label={{ value: xLabel, position: "insideBottom", offset: -16, fill: "var(--ink-2)", fontSize: 12 }}
          />
          <YAxis
            scale={yScale}
            domain={yDomain}
            ticks={yTicks}
            tickFormatter={yFormat}
            width={56}
            {...axisProps}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "var(--ink-2)", fontSize: 12, dy: 40 }}
          />
          <Tooltip
            content={<ChartTooltip labelFormatter={(x) => `${xLabel}: ${xFormat(x)}`}
                                   valueFormatter={(v) => yFormat(v)} />}
            cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
          />
          {reference && (
            <ReferenceLine y={reference.value} stroke="var(--critical)" strokeWidth={1.5}
                           label={{ value: reference.label, position: "insideTopRight", fill: "var(--ink-2)", fontSize: 11 }} />
          )}
          {series.map((s) =>
            s.theoryKey ? (
              <Line key={`${s.key}-theory`} dataKey={s.theoryKey} name={`${s.name} (theory)`}
                    stroke={s.color} strokeWidth={2} strokeDasharray="5 4" dot={false}
                    activeDot={false} isAnimationActive={false} connectNulls />
            ) : null,
          )}
          {series.map((s) => (
            <Line key={s.key} dataKey={s.key} name={`${s.name} (measured)`} stroke={s.color}
                  strokeWidth={2} isAnimationActive={false} connectNulls
                  dot={{ r: 4, fill: s.color, stroke: "var(--surface)", strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: s.color, stroke: "var(--surface)", strokeWidth: 2 }}>
              {s.errKey && <ErrorBar dataKey={s.errKey} width={6} strokeWidth={1.5} stroke={s.color} direction="y" />}
            </Line>
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
