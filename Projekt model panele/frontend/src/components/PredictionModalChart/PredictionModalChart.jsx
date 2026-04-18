import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import styles from './PredictionModalChart.module.css'

const DATA = [
  { hour: 0,  production: 0 },
  { hour: 1,  production: 0 },
  { hour: 2,  production: 0 },
  { hour: 3,  production: 0 },
  { hour: 4,  production: 0 },
  { hour: 5,  production: 0 },
  { hour: 6,  production: 1 },
  { hour: 7,  production: 6 },
  { hour: 8,  production: 16 },
  { hour: 9,  production: 28 },
  { hour: 10, production: 38 },
  { hour: 11, production: 31 },
  { hour: 12, production: 47 },
  { hour: 13, production: 45 },
  { hour: 14, production: 36 },
  { hour: 15, production: 28 },
  { hour: 16, production: 18 },
  { hour: 17, production: 9 },
  { hour: 18, production: 3 },
  { hour: 19, production: 1 },
  { hour: 20, production: 0 },
  { hour: 21, production: 0 },
  { hour: 22, production: 0 },
  { hour: 23, production: 0 },
]

function PredictionModalChart() {
  return (
    <div>
      <p className={styles.title}>PRODUKCJA GODZINOWA (MW)</p>
      <div className={styles.chartContainer}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={DATA} barCategoryGap="20%">
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
              formatter={(value) => [`${value} MW`, 'Produkcja']}
              labelFormatter={(hour) => `${hour}:00`}
              cursor={{ fill: 'rgba(255,255,255,0.05)' }}
            />
            <Bar dataKey="production" fill="#f8027c" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default PredictionModalChart
