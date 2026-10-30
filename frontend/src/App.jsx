import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001'
import Map from './components/Map/Map'
import PredictionModal from './components/PredictionModal/PredictionModal'

function App() {
  const [selectedCity, setSelectedCity] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchCity = async (city) => {
    setLoading(true);
    try {
      const { data } = await axios.post(`${API_URL}/analyze`, {
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
