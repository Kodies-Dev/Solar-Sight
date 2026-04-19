import { Text } from '@mantine/core'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import WeatherIcon from '../WeatherIcon/WeatherIcon'
import styles from './PredictionModalChart.module.css'

function CustomTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null

  const d = payload[0].payload

  return (
    <div className={styles.tooltip}>
      <Text size="xs" c="dimmed" mb={4}>{d.hour}:00</Text>
      <div className={styles.tooltipRow}>
        <WeatherIcon code={d.weather_code} size={22} />
        <Text size="xs">{d.temperature_c.toFixed(0)}°C</Text>
        <Text size="xs" c="dimmed">{d.cloud_cover_pct}%</Text>
      </div>
      <Text size="sm" fw={500} style={{ color: '#f8027c' }}>
        {d.predykcja_mwh.toFixed(2)} MWh
      </Text>
    </div>
  )
}

function PredictionModalChart({ city }) {

  return (
    <div>
      <Text size="md" fw={500}>PRODUKCJA GODZINOWA (MWh)</Text>
      <div className={styles.chartContainer}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={city.forecast} barCategoryGap="10%">
            <XAxis
              dataKey="hour"
              tickFormatter={h => `${h}:00`}
              ticks={[0, 3, 6, 9, 12, 15, 18, 21]}
              tick={{ fill: '#111', fontSize: 14 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis hide />
            <Tooltip
              content={<CustomTooltip />}
              cursor={false}
            />
            <Bar dataKey="predykcja_mwh" fill="#f8027c" radius={[3, 3, 0, 0]} activeBar={{ fill: '#d4026a' }} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default PredictionModalChart
