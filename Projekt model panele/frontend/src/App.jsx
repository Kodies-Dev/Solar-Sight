import { useState } from 'react'
import Map from './components/Map/Map'
import PredictionModal from './components/PredictionModal/PredictionModal'

function App() {
  const [selectedCity, setSelectedCity] = useState(null);

  const handleCityClick = (city) => {
    setSelectedCity(city);
  }

  const handleClose = () => {
    setSelectedCity(null);
  }

  return (
    <>
      <Map onCityClick={handleCityClick} />
      {selectedCity && (
        <PredictionModal city={selectedCity} onClose={handleClose} />
      )}
    </>
  )
}

export default App
