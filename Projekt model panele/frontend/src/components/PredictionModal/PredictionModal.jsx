import { Modal } from '@mantine/core'
import PredictionModalStats from '../PredictionModalStats/PredictionModalStats'
import PredictionModalChart from '../PredictionModalChart/PredictionModalChart'
import styles from './PredictionModal.module.css'

function PredictionModal({ city, onClose }) {
  const time = new Date().toLocaleString('pl-PL', {
    hour: '2-digit',
    minute: '2-digit',
    day: 'numeric',
    month: 'long'
  })

  return (
    <Modal
      opened={!!city}
      onClose={onClose}
      title={
        <div>
          <p className={styles.title}>{ city?.name }</p>
          <p className={styles.time}>{ time }</p>
        </div>
      }
      centered
      size="lg"
      styles={{
        header: {
          alignItems: 'flex-start',
        },
        close: {
          marginTop: '0px',
        }
      }}
    >
      {city && (
        <>
          <PredictionModalStats />
          <PredictionModalChart />
        </>
      )}
    </Modal>
  )
}

export default PredictionModal
