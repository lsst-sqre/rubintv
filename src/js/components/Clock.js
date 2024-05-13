import React, { useState, useEffect } from 'react'

export default function Clock () {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timerId = setInterval(() => {
      setTime(new Date())
    }, 1000)

    return () => {
      clearInterval(timerId)
    }
  }, [])

  const hoursMins = getHoursAndMins(time)
  const secs = padZero(time.getUTCSeconds())
  return (
    <div id='clock'>
      <div className='clockWrap'>
        <span className='hours-mins'>{hoursMins}</span>
        <span className='secs'>{secs}</span>
      </div>
    </div>
  )
}

function getHoursAndMins (time) {
  const h = padZero(time.getUTCHours())
  const m = padZero(time.getUTCMinutes())
  return h + ':' + m
}

function padZero (num) {
  return (num + 100).toString().slice(-2)
}
