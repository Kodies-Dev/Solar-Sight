import { Text, Stack } from '@mantine/core'
import WeatherIcon from '../WeatherIcon/WeatherIcon'
import styles from './PredictionWeatherForecast.module.css'

function PredictionWeatherForecast({ city }) {

  const slots = city.forecast
    .filter(d => [6, 9, 12, 15, 18, 21].includes(d.hour))
    .sort((a, b) => a.hour - b.hour)

  return (
    <Stack gap="xs">
      <Text size="lg">POGODA GODZINOWA</Text>
      <div className={styles.strip}>
        {slots.map(d => (
          <div key={d.hour} className={styles.slot}>
            <Text size="xs" c="dimmed">{d.hour}:00</Text>
            <WeatherIcon code={d.weather_code} size={32} />
            <Text size="xs" fw={500}>{d.temperature_c.toFixed(0)}°C</Text>
            <Text size="xs" c="dimmed">{d.cloud_cover_pct}%</Text>
          </div>
        ))}
      </div>
    </Stack>
  )
}

export default PredictionWeatherForecast
