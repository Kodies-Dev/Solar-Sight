import { useState } from 'react'
import axios from 'axios'
import Map from './components/Map/Map'
import PredictionModal from './components/PredictionModal/PredictionModal'

function App() {
  const [selectedCity, setSelectedCity] = useState(null);
  const [loading, setLoading] = useState(false)

  const handleCityClick = async (city) => {
    setLoading(true);
    console.log('wysyłam city:', city.id)
    try {
      const { data } = await axios.post('http://localhost:5001/analyze', {
        city: city.name
      })
      setSelectedCity({
        id: city.id,
        name: city.name,
        forecast: data.data
      })
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
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
