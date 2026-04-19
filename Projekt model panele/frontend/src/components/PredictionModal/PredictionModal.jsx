import { Title, Text, Slider } from '@mantine/core'
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
      <div className={styles.blob1} />
      <div className={styles.blob2} />
      <div className={styles.blob3} />
      {city && (
        <div className={styles.content}>
          <div className={styles.header}>
            <Title order={1}>{ city.name }</Title>
            <Text size="md" tt="uppercase" fw={500}>{time} · godz. {new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })}</Text>
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
