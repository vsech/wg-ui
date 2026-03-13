import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiService } from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const user = ref(null)
  const loginLoading = ref(false)
  const error = ref(null)

  const isAuthenticated = computed(() => !!token.value)

  const applyToken = (nextToken) => {
    token.value = nextToken

    if (nextToken) {
      localStorage.setItem('token', nextToken)
      apiService.setToken(nextToken)
      return
    }

    localStorage.removeItem('token')
    apiService.setToken(null)
  }

  const login = async (credentials) => {
    loginLoading.value = true
    error.value = null

    try {
      const response = await apiService.login(credentials)
      applyToken(response.access_token)
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || 'Login failed'
      return false
    } finally {
      loginLoading.value = false
    }
  }

  const logout = () => {
    applyToken(null)
    user.value = null
  }

  if (token.value) {
    apiService.setToken(token.value)
  }

  const handleUnauthorized = () => {
    logout()
  }

  return {
    token,
    user,
    loginLoading,
    error,
    isAuthenticated,
    login,
    logout,
    handleUnauthorized
  }
})
