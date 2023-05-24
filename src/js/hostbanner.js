import { _elWithAttrs, _elWithClass } from './modules/utils.js'

window.addEventListener('DOMContentLoaded',
  () => {
    const display = []
    if (window.location.hostname === 'localhost') {
      display.push('localhost')
    }
    if (window.location.pathname.includes('-dev')) {
      display.push('development')
    }
    if (display.length > 0) {
      const displayEl = document.createElement('div')
      displayEl.className = 'site-host-display'
      display.forEach((c) => displayEl.classList.add(c))
      const text = document.createTextNode(display.join(' '))
      displayEl.appendChild(text)
      document.body.append(displayEl)
    }
    addClock()
  }
)

function addClock () {
  const clock = _elWithAttrs('div', { id: 'clock' })
  const hm = _elWithClass('span', 'hours-mins')
  const secs = _elWithClass('span', 'secs')
  const clockEls = { hm, secs, displayed: false }
  clock.append(hm, secs)

  document.querySelector('.header-page-buttons').append(clock)

  window.setInterval(() => {
    updateClock(clockEls)
  }, 1000)

  window.addEventListener('showClock', () => {
    clock.classList.add('show')
  })
}

function updateClock (clockEls) {
  const d = new Date()
  clockEls.hm.textContent = getHoursAndMins(d)
  clockEls.secs.textContent = padZero(d.getUTCSeconds())
  if (!clockEls.displayed) {
    window.dispatchEvent(new Event('showClock'))
    clockEls.displayed = true
  }
}

function getHoursAndMins (dateObj) {
  const h = padZero(dateObj.getUTCHours())
  const m = padZero(dateObj.getUTCMinutes())
  return h + ':' + m
}

function padZero (num) {
  return (num + 100).toString().slice(-2)
}
