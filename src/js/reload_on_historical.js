import { _getById } from './modules/utils.js'
import { WebsocketClient } from './modules/websocket_client.js'
/*
Listens for the status of the historical poller via an event from the websocket
client if the #historicalBusy element shows that historical data for the site
is still loading. Reloads the page once notified that historical data is ready.
*/

window.addEventListener('load', () => {
  if ((_getById('historicalbusy') && _getById('historicalbusy').dataset.historicalbusy === 'False') ||
  !_getById('historicalbusy')) {
    return
  }
  // eslint-disable-next-line no-unused-vars
  const ws = new WebsocketClient('historicalStatus')
  window.addEventListener('historicalStatus', (message) => {
    console.log('event message:', message)
    const isBusy = message.detail.data
    if (!isBusy) {
      window.location.reload()
    }
  })
})

// export function waitForHistoricalStatus () {
//   return new Promise((resolve, reject) => {
//     const historicalBusyElement = _getById('historicalbusy')
//     if (historicalBusyElement && historicalBusyElement.dataset.historicalbusy === 'False') {
//       resolve()
//       return
//     }
//     // eslint-disable-next-line no-unused-vars
//     const ws = new WebsocketClient('historicalStatus')
//     window.addEventListener('historicalStatus', (message) => {
//       const isBusy = message.data
//       if (!isBusy) {
//         resolve()
//       }
//     })
//   })
// }
