import { Title, Text } from '@mantine/core'
import PredictionModalStats from '../PredictionModalStats/PredictionModalStats'
import PredictionModalChart from '../PredictionModalChart/PredictionModalChart'
import PredictionWeatherForecast from '../PredictionWeatherForecast/PredictionWeatherForecast'
import styles from './PredictionModal.module.css'

function PredictionModal({ city }) {
  const time = new Date().toLocaleString('pl-PL', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return (
    <div className={styles.sidebar}>
      {city && (
        <div className={styles.content}>
          <div className={styles.header}>
            <Title order={1}>{ city.name }</Title>
            <Text size="lg">{ time }</Text>
          </div>
          <PredictionModalStats city={city} />
          <PredictionModalChart city={city} />
          <PredictionWeatherForecast city={city} />
        </div>
      )}
    </div>
  )
}

export default PredictionModal
