import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiService } from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const user = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const isAuthenticated = computed(() => !!token.value)

  const login = async (credentials) => {
    loading.value = true
    error.value = null

    try {
      const response = await apiService.login(credentials)
      token.value = response.access_token
      localStorage.setItem('token', response.access_token)

      // Set token for future API calls
      apiService.setToken(response.access_token)

      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Login failed'
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    apiService.setToken(null)
  }


  // Initialize token on store creation
  if (token.value) {
    apiService.setToken(token.value)
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    login,
    logout
  }
})
