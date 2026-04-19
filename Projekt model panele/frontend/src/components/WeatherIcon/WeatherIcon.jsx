import {WiCloudy, WiDayCloudy, WiDaySunny, WiFog, WiRain, WiSnow, WiThunderstorm} from "react-icons/wi";

function WeatherIcon({ code, size = 32 }) {
  const props = { size, color: '#f8027c' }

  if (code === 0) return <WiDaySunny {...props} />
  if (code <= 2)  return <WiDayCloudy {...props} />
  if (code === 3) return <WiCloudy {...props} color="#888" />
  if ([45, 48].includes(code)) return <WiFog {...props} color="#888" />
  if ([71, 73, 75].includes(code)) return <WiSnow {...props} color="#378ADD" />
  if ([51,53,55,61,63,65,80,81,82].includes(code)) return <WiRain {...props} color="#378ADD" />
  if ([95,96,99].includes(code)) return <WiThunderstorm {...props} />

  return <WiCloudy size={size} color="#aaa" />
}

export default WeatherIcon
