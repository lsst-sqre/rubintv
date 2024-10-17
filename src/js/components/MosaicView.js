import React, { useState, useEffect } from "react"
import PropTypes from "prop-types"
import { WebsocketClient } from "../modules/ws-service-client"
import {
  cameraType,
  channelDataType,
  eventType,
  metadataType,
  mosaicSingleView,
} from "./componentPropTypes"
import { simpleGet } from "../modules/utils"

const commonColumns = ["seqNum"]

export default function MosaicView({ locationName, camera, initialDate }) {
  const [historicalBusy, setHistoricalBusy] = useState(null)
  const [currentMeta, setCurrentMeta] = useState(null)
  const [date, setDate] = useState(initialDate)

  const initialViews = camera.mosaic_view_meta.map(view => (
    {
      ...view,
      dayObs: null,
      latestEvent: {},
      latestMetadata: {}
    }))
  const [views, setViews] = useState(initialViews)

  useEffect(() => {
    function handleMetadataChange (event) {
      const { datestamp, data, dataType } = event.detail
      if (Object.entries(data).length < 1 || dataType !== 'metadata') {
        return
      }
      console.debug("Got metadata!", data)
    }
    window.addEventListener('camera', handleMetadataChange)
    return () => {
      window.removeEventListener('camera', handleMetadataChange)
    }
  })

  useEffect(() => {
    function handleHistoricalStateChange (event) {
      const { data: historicalBusy } = event.detail
      setHistoricalBusy( historicalBusy )
    }
    window.addEventListener('historicalStatus', handleHistoricalStateChange)
    return () => {
      window.removeEventListener('historicalStatus', handleHistoricalStateChange)
    }
  })

  useEffect(() => {
    function handleChannelEvent (event) {
      const { datestamp, data } = event.detail
      if (!data) {
        return
      }
      const { channel_name: chanName } = data
      setViews((prevViews) =>
        prevViews.map(view =>
          view.channel === chanName ? { ...view, dayObs: datestamp, latestEvent: data } : view))
    }
    window.addEventListener('channel', handleChannelEvent)
  
    // Cleanup the event listener on component unmount
    return () => {
      window.removeEventListener('channel', handleChannelEvent)
    }
  })

  return (
    <div className="viewsArea">
      <h3 className="viewsTitle">Mosaic View: <span className="date">{date}</span></h3>
      <ul className="views">
        {views.map((view) => {
          return (
            <li key={view.channel} className="view">
              <ChannelView locationName={locationName} camera={camera} view={view} />
            </li>
          )
        })}
      </ul>
    </div>
  )
}
MosaicView.propTypes = {
  locationName: PropTypes.string,
  camera: cameraType,
  initialDate: PropTypes.string,
}

function ChannelView({ locationName, camera, view }) {
  let channel
  try {
    channel = camera.channels.filter(({name}) => name === view.channel)[0]
  } catch (error) {
    return (
      <h3>Channel { view.channel } not found</h3>
    )
  }
  return (
    <>
      <h3 className="channel">{ channel.title } - { view.dayObs }</h3>
      <ChannelImage locationName={locationName} camera={camera} event={view.latestEvent} />
      <ChannelMetadata viewMetaColumns={view.metaColumns} metadata={view.latestMetadata} />
    </>
  )
}
ChannelView.propTypes = {
  locationName: PropTypes.string,
  camera: cameraType,
  view: mosaicSingleView,
}


function ChannelImage({ locationName, camera, event }) {
  const { filename } = event
  const relUrl = buildImageURI(locationName, camera.name, event.channel_name, filename)
  const imgSrc = new URL(`event_image/${relUrl}`, APP_DATA.baseUrl)
  if (filename) {
    return (
      <div className="viewImage">
        <a href={imgSrc}>
          <img className="resp" src={imgSrc}/>
        </a>
      </div>
    )
  } else {
    return (
      <div className="viewImage">
      </div>
    )
  }
}
ChannelImage.propTypes = {
  locationName: PropTypes.string,
  camera: cameraType,
  event: eventType,
}

function ChannelMetadata({ viewMetaColumns, metadata }) {
  const columns = [...commonColumns, ...viewMetaColumns]
  return (
    <ul className="viewMeta">
      {columns.map((column) => {
        const value = metadata[column] ? metadata[column] : "No value set"
        return (
           <li key={column} className="viewMetaCol">
            <div className="colName">{column}</div>
            <div className="colValue">{value}</div>
           </li>
        )
      })}
    </ul>
  )
}
ChannelMetadata.propTypes = {
  viewMetaColumns: PropTypes.arrayOf(PropTypes.string),
  metadata: metadataType,
}

const buildImageURI = (locationName, cameraName, channelName, filename) =>
  `${locationName}/${cameraName}/${channelName}/${filename}`
