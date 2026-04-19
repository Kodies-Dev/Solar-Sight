import { useRef, useEffect } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import styles from './Map.module.css'
import citiesData from '../../data/cities.json'

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

function Map({ onCityClick }) {
  const mapRef = useRef(null);
  const mapContainerRef = useRef(null);

useEffect(() => {
  mapboxgl.accessToken = MAPBOX_ACCESS_TOKEN;

  mapRef.current = new mapboxgl.Map({
    container: mapContainerRef.current,
    style: 'mapbox://styles/mapbox/light-v11',
    center: [18.67796034218694, 50.28883369377393],
    zoom: 8,
    minZoom: 6,
    maxBounds: [
      [13.8, 48.9],
      [24.2, 55.0]
    ],
    attributionControl: false
  })

  mapRef.current.addControl(
    new mapboxgl.AttributionControl({
      compact: true
    }),
    'bottom-right'
  );

  mapRef.current.on('load', () => {
    mapRef.current.addSource('cities', {
      type: 'geojson',
      data: citiesData
    })

    mapRef.current.addLayer({
      id: 'cities-dots-glow',
      type: 'circle',
      source: 'cities',
      paint: {
        'circle-radius': 20,
        'circle-color': '#f8027c',
        'circle-opacity': 0.2,
        'circle-blur': 2,
      }
    })

    mapRef.current.addLayer({
      id: 'cities-dots',
      type: 'circle',
      source: 'cities',
      paint: {
        'circle-radius': 8,
        'circle-color': '#f8027c',
        'circle-stroke-color': '#f8027c',
        'circle-stroke-width': 2,
      }
    })

    mapRef.current.on('mouseenter', 'cities-dots', () => {
      mapRef.current.getCanvas().style.cursor = 'pointer'
    })

    mapRef.current.on('mouseleave', 'cities-dots', () => {
      mapRef.current.getCanvas().style.cursor = ''
    })

    mapRef.current.on('click', 'cities-dots', (e) => {
      const city = e.features[0].properties
      onCityClick(city);
    })
  })

  return () => {
    mapRef.current.remove();
  }
}, [])

  return (
    <>
      <div className={styles.mapContainer} ref={mapContainerRef}></div>
    </>
  )
}

export default Map
