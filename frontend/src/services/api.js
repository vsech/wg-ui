import axios from 'axios'

class ApiService {
  constructor() {
    this.baseURL = '/api'
    this.client = axios.create({
      baseURL: this.baseURL,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor to handle auth errors
    this.client.interceptors.response.use(
      (response) => response.data,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  setToken(token) {
    if (token) {
      this.client.defaults.headers.Authorization = `Bearer ${token}`
    } else {
      delete this.client.defaults.headers.Authorization
    }
  }

  // Auth endpoints
  async login(credentials) {
    return await this.client.post('/auth/login', credentials)
  }


  // Client endpoints
  async getClients() {
    return await this.client.get('/clients')
  }

  async createClient(clientData) {
    return await this.client.post('/clients', clientData)
  }

  async deleteClient(clientName) {
    return await this.client.delete(`/clients/${clientName}`)
  }

  async getClientConfig(clientName) {
    return await this.client.get(`/clients/${clientName}/config`)
  }

  async getClientQR(clientName) {
    return await this.client.get(`/clients/${clientName}/qr`)
  }
}

export const apiService = new ApiService()
