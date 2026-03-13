import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { apiService } from '@/services/api'

export const useClientsStore = defineStore('clients', () => {
  const clients = ref([])
  const clientDetails = ref({})
  const listLoading = ref(false)
  const createLoading = ref(false)
  const deleteLoading = reactive({})
  const detailsLoading = reactive({})
  const error = ref(null)

  const fetchClients = async () => {
    listLoading.value = true
    error.value = null

    try {
      const response = await apiService.getClients()
      clients.value = response
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch clients'
    } finally {
      listLoading.value = false
    }
  }

  const createClient = async (clientData) => {
    createLoading.value = true
    error.value = null

    try {
      const response = await apiService.createClient(clientData)
      clientDetails.value = {
        ...clientDetails.value,
        [response.name]: response,
      }
      await fetchClients()
      return response
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to create client'
      throw err
    } finally {
      createLoading.value = false
    }
  }

  const deleteClient = async (clientName) => {
    deleteLoading[clientName] = true
    error.value = null

    try {
      await apiService.deleteClient(clientName)
      const nextDetails = { ...clientDetails.value }
      delete nextDetails[clientName]
      clientDetails.value = nextDetails
      await fetchClients()
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to delete client'
      return false
    } finally {
      deleteLoading[clientName] = false
    }
  }

  const fetchClientDetails = async (clientName, { force = false } = {}) => {
    if (!force && clientDetails.value[clientName]) {
      return clientDetails.value[clientName]
    }

    detailsLoading[clientName] = true
    error.value = null

    try {
      const response = await apiService.getClientConfig(clientName)
      clientDetails.value = {
        ...clientDetails.value,
        [clientName]: response,
      }
      return response
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load client config'
      throw err
    } finally {
      detailsLoading[clientName] = false
    }
  }

  const isDeleting = (clientName) => !!deleteLoading[clientName]
  const isDetailsLoading = (clientName) => !!detailsLoading[clientName]

  return {
    clients,
    clientDetails,
    listLoading,
    createLoading,
    error,
    fetchClients,
    createClient,
    deleteClient,
    fetchClientDetails,
    isDeleting,
    isDetailsLoading
  }
})
