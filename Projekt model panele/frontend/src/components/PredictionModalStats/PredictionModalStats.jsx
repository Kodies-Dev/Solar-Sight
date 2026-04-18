import { Paper, Text } from '@mantine/core'
import styles from './PredictionModalStats.module.css'

const stats = [
  { label: 'Łącznie dziś', value: '200 MWh' },
  { label: 'Szczyt', value: '40,2 MWh' },
  { label: 'Godzina szczytu', value: '200 MWh' },
]

function PredictionModalStats() {
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
