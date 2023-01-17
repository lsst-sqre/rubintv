import { TableControls } from '../modules/table-control.js'
import { parseJsonFromDOM } from '../modules/utils.js'
import { slacDefault } from '../models.js'
import { addToTable } from '../modules/table-auxtel.js'
import { applyYearControls } from '../modules/calendar-controls.js'

document.addEventListener('DOMContentLoaded', () => {
  const meta = parseJsonFromDOM('#table-metadata')
  const tableUI = new TableControls(slacDefault, meta, '.channel-grid-heading', addToTable)
  addToTable(meta, tableUI.selected)
  applyYearControls()
})
