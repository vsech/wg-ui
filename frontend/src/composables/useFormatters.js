export function useFormatters() {
  const formatDate = (dateString) => {
    if (!dateString) return 'Never'
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return 'Never'
    return date.toLocaleDateString()
  }

  const formatDateTime = (dateTimeString) => {
    if (!dateTimeString) return 'Never'
    const date = new Date(dateTimeString)
    if (Number.isNaN(date.getTime())) return 'Never'
    return date.toLocaleString()
  }

  const formatBytes = (bytes) => {
    if (!bytes || bytes <= 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let unitIndex = 0
    let value = bytes

    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024
      unitIndex += 1
    }

    return `${value.toFixed(value < 10 && unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`
  }

  return {
    formatDate,
    formatDateTime,
    formatBytes,
  }
}
