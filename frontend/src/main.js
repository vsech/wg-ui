import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { apiService } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

// UIkit CSS and JS
import 'uikit/dist/css/uikit.min.css'
import UIkit from 'uikit'
import Icons from 'uikit/dist/js/uikit-icons'

// Load UIkit icons
UIkit.use(Icons)

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const authStore = useAuthStore(pinia)
apiService.setUnauthorizedHandler(async () => {
  authStore.handleUnauthorized()
  if (router.currentRoute.value.path !== '/login') {
    await router.push('/login')
  }
})

app.mount('#app')
