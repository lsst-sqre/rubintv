import { _getById } from './modules/utils.js'

window.addEventListener('pageshow', function (e) {
  const location = _getById('location').dataset.location

  // scrape relevent services from page
  const serviceEls = Array.from(document.querySelectorAll('.service'))
  const services = serviceEls.map(s => {
    return { id: s.id, el: s, dependentOn: s.dataset.dependentOn }
  })

  // boil down dependency names
  const dependenciesNames = Array.from(
    new Set(
      services.map(service => { return service.dependentOn })
        // filter out any undefined or empty dependencies
        .filter(serviceName => { return serviceName })
    )
  )

  // init websocket listener
  const protocol = this.document.protocol
  const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:'
  // use origin to include port
  const hostname = this.document.location.origin.split('//')[1]
  const appName = this.document.location.pathname.split('/')[1]
  const wsUrl = `${wsProtocol}//${hostname}/${appName}/${location}/heartbeats_ws`

  let retry
  let webSocket = new WebSocket(wsUrl)

  webSocket.onopen = () => {
    console.log('Listening for heartbeats...')
  }

  webSocket.onmessage = heartbeatHandler

  function heartbeatHandler (event) {
    const heartbeats = JSON.parse(event.data)
    services.forEach(s => {
      const hb = heartbeats[s.id]

      const hasDependent = s.dependentOn && dependenciesNames.includes(s.dependentOn)
      const depActive = hasDependent ? heartbeats[s.dependentOn].active : true
      const status = hb.active && depActive ? 'active' : 'stopped'

      let msg = `last heartbeat at: ${timestampToDateUTC(hb.curr)} UTC`
      msg = msg.concat(`\nnext check at: ${timestampToDateUTC(hb.next)} UTC`)
      if (!depActive) {
        msg = msg.concat(`\nDependency: ${s.dependentOn} is stopped`)
      }

      s.el.classList.remove('active', 'stopped')
      s.el.classList.add(status)
      s.el.setAttribute('title', msg)
    })
  }

  webSocket.onclose = () => {
    let count = 0
    retry = this.setInterval(() => {
      try {
        webSocket = new WebSocket(wsUrl)
        console.log(`count is ${count}`)
        webSocket.onopen = () => {
          this.clearInterval(retry)
          webSocket.onmessage = heartbeatHandler
          console.log('Listening for heartbeats...')
        }
      } catch (error) {
        console.error('Websocket closed. Trying to reopen...')
      } finally {
        count++
      }
    }, 5000)
  }

  function timestampToDateUTC (timestamp) {
    // Date takes timestamp in milliseconds
    const d = new Date(timestamp * 1000).toLocaleString('en-US', { timeZone: 'UTC' })
    return d
  }
})
