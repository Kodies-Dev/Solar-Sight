import { Paper, Text } from '@mantine/core'
import styles from './PredictionModalStats.module.css'

function PredictionModalStats({ city }) {
  const total = city.forecast.reduce((sum, d) => sum + d.predykcja_mwh, 0).toFixed(2)
  const peak = Math.max(...city.forecast.map(d => d.predykcja_mwh)).toFixed(2)
  const peakHour = city.forecast.reduce((max, d) => d.predykcja_mwh > max.predykcja_mwh ? d : max).hour

  const stats = [
    { label: 'Przewidywana produkcja', value: `${total} MWh` },
    { label: 'Maks. produkcja godzinowa', value: `${peak} MWh` },
    { label: 'Godzina szczytu', value: `${peakHour}:00` },
  ]

  return (
    <div className={styles.statsContainer}>
      {stats.map(({label, value}) => (
        <Paper key={label} className={styles.statsCard}>
          <Text className={styles.statsLabel}>{ label }</Text>
          <Text className={styles.statsValue}>{ value }</Text>
          <Text></Text>
        </Paper>
      ))}
    </div>
  )
}

export default PredictionModalStats
