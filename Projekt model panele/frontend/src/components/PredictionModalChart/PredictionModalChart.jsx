import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import styles from './PredictionModalChart.module.css'

function PredictionModalChart({ city }) {
  return (
    <div>
      <p className={styles.title}>PRODUKCJA GODZINOWA (MW)</p>
      <div className={styles.chartContainer}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={city.forecast} barCategoryGap="20%">
            <XAxis
              dataKey="hour"
              tickFormatter={h => `${h}:00`}
              ticks={[0, 6, 12, 18, 23]}
              tick={{ fill: '#aaa', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis hide />
            <Tooltip
              formatter={(value) => [`${value.toFixed(2)} MWh`, 'Produkcja']}
              labelFormatter={(hour) => `${hour}:00`}
              cursor={{ fill: 'rgba(255,255,255,0.05)' }}
            />
            <Bar dataKey="predykcja_mwh" fill="#f8027c" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default PredictionModalChart
