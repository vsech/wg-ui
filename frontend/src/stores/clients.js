import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiService } from '@/services/api'

export const useClientsStore = defineStore('clients', () => {
  const clients = ref([])
  const loading = ref(false)
  const error = ref(null)

  const fetchClients = async () => {
    loading.value = true
    error.value = null

    try {
      const response = await apiService.getClients()
      clients.value = response
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch clients'
    } finally {
      loading.value = false
    }
  }

  const createClient = async (clientData) => {
    loading.value = true
    error.value = null

    try {
      const response = await apiService.createClient(clientData)
      await fetchClients() // Refresh the list
      return response
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to create client'
      throw err
    } finally {
      loading.value = false
    }
  }

  const deleteClient = async (clientName) => {
    loading.value = true
    error.value = null

    try {
      await apiService.deleteClient(clientName)
      await fetchClients() // Refresh the list
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to delete client'
      return false
    } finally {
      loading.value = false
    }
  }

  const getClientQR = async (clientName) => {
    loading.value = true
    error.value = null

    try {
      const response = await apiService.getClientQR(clientName)
      return response.qr_code
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to generate QR code'
      throw err
    } finally {
      loading.value = false
    }
  }

  const getClientConfig = async (clientName) => {
    loading.value = true
    error.value = null

    try {
      const response = await apiService.getClientConfig(clientName)
      return response
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load client config'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    clients,
    loading,
    error,
    fetchClients,
    createClient,
    deleteClient,
    getClientQR,
    getClientConfig
  }
})
