import React, { useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import { cameraType, eventType } from './componentPropTypes'

function PerDayChannels ({ camera, date, perDay }) {
  const baseUrl = window.APP_DATA.baseUrl
  const locationName = document.documentElement.dataset.locationname
  const channels = camera.channels
  return (
    (perDay && Object.entries(perDay).length > 0) && (
      <nav id="per-day-menu" className="channel-menu" role="navigation">
      <h3>Per Day Channels</h3>
        <ul className="channels flr">
          { Object.entries(perDay).map(([channelName, event]) => {
            const channel = channels[channels.map((chan) => chan.name).indexOf(channelName)]
            const label = channel.label ? channel.label : channel.title
            const filename = event.filename
            return (
              <li className="channel" key={channelName}>
                <a
                  className={`button button-large ${channelName}`}
                  href={`${baseUrl}event_video/${locationName}/${camera.name}/${channelName}/${filename}`}
                  style={
                    { backgroundColor: channel.colour }
                  }
                >
                  <img src={`${baseUrl}static/images/${channelName}.svg`} />
                  {label}
                  <span className="date">{ date }</span>
                </a>
              </li>
            )
          })}
        </ul>
      </nav>
    )
  )
}
PerDayChannels.propTypes = {
  /** The current camera.
   */
  camera: cameraType,
  /** perDay is an object with channel names as keys and single events as
   * values.
   */
  perDay: PropTypes.objectOf(eventType),
  /** The chosen date. */
  date: PropTypes.string
}

function NightReportLink ({ camera, date, nightReportExists, isToday }) {
  if (!nightReportExists) {
    return null
  }
  const baseUrl = window.APP_DATA.baseUrl
  const locationName = document.documentElement.dataset.locationname
  let label
  let link
  if (isToday) {
    link = `${baseUrl}${locationName}/${camera.name}/night_report`
    label = camera.night_report_label
  } else {
    link = `${baseUrl}${locationName}/${camera.name}/night_report/${date}`
    label = `${camera.night_report_label} for ${date}`
  }
  return (
    <div id="night_report_link">
      <h3>Night Report</h3>
      <a
        className="button button-large night-report"
        href={link}>
          <img src={`${baseUrl}static/images/crescent-moon.svg`} />
          {label}
      </a>
    </div>
  )
}
NightReportLink.propTypes = {
  camera: cameraType,
  date: PropTypes.string,
  nightReportExists: PropTypes.bool,
  isToday: PropTypes.bool
}

export default function PerDay ({ camera, initialDate, initialPerDay, initialNRExists, initialIsToday }) {
  const [date, setDate] = useState(initialDate)
  const [perDay, setPerDay] = useState(initialPerDay)
  const [nightReportExists, setNightReportExists] = useState(initialNRExists)
  const [isToday, setIsToday] = useState(initialIsToday)

  useEffect(() => {
    function handleCameraEvent (event) {
      const { datestamp, data, dataType } = event.detail

      if (datestamp && datestamp !== date) {
        setDate(datestamp)
      }

      if (dataType === 'per_day' && data != "nightReportExists") {
        setPerDay(data)
      }
      else if (dataType === 'per_day' && data == "nightReportExists") {
        setNightReportExists(true)
      }
    }
    window.addEventListener('camera', handleCameraEvent)

    // Cleanup the event listener on component unmount
    return () => {
      window.removeEventListener('camera', handleCameraEvent)
    }
  }, [date]) // Only reattach the event listener if the date changes

  return (
    <>
      <PerDayChannels camera={camera} date={date} perDay={perDay} />
      <NightReportLink
      camera={camera}
      date={date}
      nightReportExists={nightReportExists}
      isToday={isToday} />
    </>
  )
}
PerDay.propTypes = {
  camera: cameraType,
  initialPerDay: PropTypes.objectOf(eventType),
  initialDate: PropTypes.string,
  /** True if a night report event exists for this date. */
  nightReportExists: PropTypes.bool,
  isToday: PropTypes.bool
}
