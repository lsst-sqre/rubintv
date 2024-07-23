import React, { useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import { nightReportData } from './componentPropTypes'
import { groupBy, sanitiseString } from '../modules/utils'

function NightReportText ({ nightReport, selected }) {
  const data = nightReport.text || {}
  const efficiency = {}
  const qaPlots = {}
  for (const[key, val] of Object.entries(data)) {
    if (key.startsWith('text_')) {
      efficiency[key] = val
    } else {
      qaPlots[key] = val
    }
  }
  let effSelected = '', qaSelected = ''
  if (selected === 'efficiency') {
    effSelected = 'selected'
  } else if (selected === 'qa_plots') {
    qaSelected = 'selected'
  }
  return (
    <>
      <div id='tabgroup-efficiency' className={`dashboard tab-content ${effSelected}`}>
        {
          Object.entries(efficiency).map(([textName, text]) => {
            // for multiline text
            if (text) {
              return (
                <ul className='dashboard-text' key={textName}>
                  <li>
                    {text.split('\n').map((line, lineNum) => {
                      if (line) {
                        return (
                            /* char code 160 is non-breaking space- used so that
                            formatted text lines up as expected. */
                            <p key={lineNum}>
                              {
                                line.replace('  ',
                                  String.fromCharCode(160) +
                                  String.fromCharCode(160))
                              }
                            </p>
                        )
                      } else {
                        return <br key={lineNum}/>
                      }
                    })}
                    </li>
                </ul>
              )
            } else {
              return null
            }
          })
        }
      </div>

      <div id='tabgroup-qa_plots' className={`qa-plots tab-content ${qaSelected}`}>
        <ul>
        {
          Object.entries(qaPlots).map(([title, link]) => {
            return (
                <li>
                  <a href={link} target='_blank'>
                    { title }
                  </a>
                </li>
            )
          })
        }
        </ul>
      </div>
    </>
  )
}
NightReportText.propTypes = {
  /**
   * NightReportText objects have keys that are either `text_${num}` for which
   * the value is a multiline text string with newline (\n) delimeters or an
   * object of link(value)/title(key) pairs.
   */
  nightReport: PropTypes.object
}

function getTabNames (nightReport) {
  let groups = ['Efficiency']
  if (nightReport.text && Object.keys(nightReport.text).filter(n => !n.startsWith('text')).length > 0) {
    groups = groups.concat('QA Plots')
  }
  const plots = nightReport.plots
  if (plots) {
    groups = groups.concat([...new Set(plots.map(nr => nr.group ))])
  }
  return groups
}


function NightReportTabs ({ nightReport, tabNames, selected, setSelected }) {
  const [hiddenTabs, setHiddenTabs] = useState(['elana'])
  const [typed, setTyped] = useState('')

  useEffect(() => {
    const keyPress = (e) => {
      const newTyped = typed + e.key
      setTyped(newTyped)

      // Check if the whole key has been typed out
      if (hiddenTabs.includes(newTyped)) {
        // Assume a function to reveal the tab and perform actions
        setSelected(newTyped)
        // Update keyCodes by removing the typed one
        const newHiddenTabs = hiddenTabs.filter(k => k !== newTyped)
        setHiddenTabs(newHiddenTabs)
        // Remove listener if no more keys are left
        if (newHiddenTabs.length === 0) {
          document.body.removeEventListener('keydown', keyPress)
        }
      } else {
        // Check if the beginning of any valid code is being typed
        const isTypingAnyKey = hiddenTabs.some(k => k.startsWith(newTyped))
        if (!isTypingAnyKey) {
          setTyped('')
        }
      }
    }

    document.body.addEventListener('keydown', keyPress)
    return () => {
      document.body.removeEventListener('keydown', keyPress)
    }
  }, [typed, hiddenTabs])



  const handleSelectionChange = (selectedGroup) => {
    const selected = sanitiseString(selectedGroup)
    setSelected(prevSelected => {
        if (selected != prevSelected) {
          localStorage.setItem('night-report-selected', selected)
        }
        return selected
      }
    )
  }
  const plots = nightReport.plots

  return (
    <div className='tab-titles'>
        { tabNames.map(tabName => {
          let isDisabled = '', isSelected = ''
          if (hiddenTabs.includes(sanitiseString(tabName))) {
            isDisabled = 'disabled'
          }
          const tabId = sanitiseString(tabName)
          if (tabId === selected) {
            isSelected = 'selected'
          }
          return (
            <div
              key={tabName}
              onClick={() => handleSelectionChange(tabName)}
              id={`tabtitle-${tabId}`}
              className={`tab-title ${isDisabled} ${isSelected}`} >
                {tabName}
            </div>
          )
        })

        }
    </div>
  )
}
NightReportTabs.propTypes = {
  nightReport:  PropTypes.exact({
    plots: PropTypes.arrayOf(PropTypes.object),
    text: PropTypes.object
  }),
  tabNames: PropTypes.arrayOf(PropTypes.string),
  selected: PropTypes.string,
  setSelected: PropTypes.func
}

function NightReportPlots ({ nightReport, selected, camera, locationName, baseUrl }) {
  const plots = nightReport.plots
  return (
    <>
      { groupBy(plots, plot => plot.group).map(([group, groupedPlots]) => {
          const groupId = sanitiseString(group)
          let isSelected = ''
          if (groupId === selected) {
            isSelected = 'selected'
          }
          return (
            <div
              key={groupId}
              id={`tabgroup-${groupId}`}
              className={`tab-content plots-grid ${isSelected}`}
            >
              { groupedPlots.map(plot => {
                const imgUrl = `${baseUrl}plot_image/${locationName}/${camera.name}/${group}/${plot.filename}`
                return (
                  <figure key={plot.hash} className='plot'>
                    <a href={imgUrl}>
                      <img src={imgUrl} alt={plot.filename} />
                    </a>
                    <figcaption>{plot.filename}</figcaption>
                  </figure>
                )
              })}
            </div>
          )
      })}
    </>
  )
}
NightReportPlots.propTypes = {
  nightReport:  PropTypes.exact({
    plots: PropTypes.arrayOf(nightReportData),
    text: PropTypes.object
  }),
  camera: PropTypes.object,
  locationName: PropTypes.string,
  baseUrl: PropTypes.string
}

function NightReport ({ initialNightReport, initialDate, camera, locationName, baseUrl }) {
  const [date, setDate] = useState(initialDate)
  const [nightReport, setNightReport] = useState(initialNightReport)

  const tabNames =  getTabNames(initialNightReport)
  const [selected, setSelected] = useState(
    () => {
      let tabIds = tabNames.map(tn => sanitiseString(tn))
      let storedSelected = localStorage.getItem('night-report-selected')
      if (!storedSelected || !(tabIds.includes(storedSelected))) {
        storedSelected = tabIds[0]
        localStorage.setItem('night-report-selected', storedSelected)
      }
      return storedSelected
    }
  )

  useEffect(() => {
    function handleNightReportEvent (event) {
      const { datestamp, data, dataType } = event.detail

      if (datestamp && datestamp !== date) {
        setDate(datestamp)
      }
      if (dataType === 'nightReport') {
        setNightReport(data)
      }
    }
    window.addEventListener('nightreport', handleNightReportEvent)

    // Cleanup the event listener on component unmount
    return () => {
      window.removeEventListener('nightreport', handleNightReportEvent)
    }
  }, [date]) // Only reattach the event listener if the date changes

  if (Object.entries(nightReport).length === 0) {
    return (
      <h3>There is no night report for today yet</h3>
    )
  }

  return (
    <>
      <h3 id='the-date'>
        {camera.night_report_label} for: {initialDate}
      </h3>

      <div className='plots-section tabs'>
          <NightReportTabs
            nightReport={nightReport}
            tabNames={tabNames}
            selected={selected}
            setSelected={setSelected} />
          <NightReportText
            nightReport={nightReport}
            selected={selected}/>
          <NightReportPlots
            nightReport={nightReport}
            selected={selected}
            camera={camera}
            locationName={locationName}
            baseUrl={baseUrl} />
      </div>
    </>
  )
}
NightReport.propTypes = {
  /** The date in 'YYYY-MM-DD' format. */
  initialDate: PropTypes.string,
  /** NightReport object has optional 'plots' and/or 'text' properties.
   *  A plot object comprises the following string attributes:
   * {
   *  'key': (string) The key of the original object in the bucket.
   *  'hash': (string) The hash of the object.
   *  'camera': (string) The camera to which the plot belongs.
   *  'day_obs': (string) The date of the plot.
   *  'group': (string) The group to which the plot belongs.
   *  'filename': (string) The filename for the plot.
   *  'ext': (string) The file extension.
   * }
   * See NightReportText above for a brief description of the 'text' object.
   */
  initialNightReport: PropTypes.exact({
    plots: PropTypes.arrayOf(nightReportData),
    text: PropTypes.object
  }),
  /** The camera object. Please see rubin-tv/src/rubintv/models/models.py
   * for a full description.
  */
  camera: PropTypes.object,
  /** The name of the camera location. */
  locationName: PropTypes.string,
  /** Absolute base URL as defined by the app. Injected from the template to
   * avoid using js string wrangling to find it. Used to construct plot paths
   * for linking to.
   */
  baseUrl: PropTypes.string
}
export default NightReport
