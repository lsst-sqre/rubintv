import { ChannelStatus } from '../modules/heartbeat.js'
import { getJson } from '../modules/utils.js'

window.addEventListener('load', () => {
  const urlPath = document.location.pathname
  const currentImage = document.querySelector('.current-still')
  const currentMovie = document.querySelector('.current-movie')

  setInterval(function refresh () {
    getJson(urlPath + '/update/image').then(data => {
      if (data.channel === 'image') {
        currentImage.querySelector('img').setAttribute('src', data.url)
        currentImage.querySelector('a').setAttribute('href', data.url)
        currentImage.querySelector('.subheader h3').textContent = `${data.date} : Image ${data.seq}`
        currentImage.querySelector('.desc').textContent = data.name
      }
    })
  }, 5000)

  const videoCheckLatest = function () {
    const video = currentMovie.querySelector('video')
    getJson(urlPath + '/update/movie').then(data => {
      const source = video.querySelector('source')
      const currentMovieUrl = source.getAttribute('src')
      if (data.channel === 'movie' && data.url !== currentMovieUrl) {
        source.setAttribute('src', data.url)
        currentMovie.querySelector('.movie-date').textContent(data.date)
        currentMovie.querySelector('.movie-number').textContent(data.seq)
        currentMovie.querySelector('.desc').textContent(data.name)
        video.load()
      }
    })
  }
  setInterval(videoCheckLatest, 5000)

  const status = new ChannelStatus('allsky')
  console.log(JSON.stringify(status))
})
