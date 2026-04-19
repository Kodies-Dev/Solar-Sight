import { useState, useEffect } from 'react'
import axios from 'axios'
import Map from './components/Map/Map'
import PredictionModal from './components/PredictionModal/PredictionModal'

function App() {
  const [selectedCity, setSelectedCity] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchCity = async (city) => {
    setLoading(true);
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

  useEffect(() => {
    fetchCity({id: 'gliwice', name: 'Gliwice'})
  }, [])

  const handleCityClick = async (city) => {
    fetchCity(city);
  }

  return (
    <>
      <Map onCityClick={handleCityClick} />
      <PredictionModal city={selectedCity} />
    </>
  )
}

export default App
