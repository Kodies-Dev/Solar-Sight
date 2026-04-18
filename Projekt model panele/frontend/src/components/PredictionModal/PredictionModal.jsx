import { Modal } from '@mantine/core'
import PredictionModalStats from '../PredictionModalStats/PredictionModalStats'
import PredictionModalChart from '../PredictionModalChart/PredictionModalChart'

function PredictionModal({ city, onClose }) {
  return (
    <Modal
      opened={!!city}
      onClose={onClose}
      title={city?.name}
      centered
      size="lg"
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
