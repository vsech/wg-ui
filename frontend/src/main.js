import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

// UIkit CSS and JS
import 'uikit/dist/css/uikit.min.css'
import UIkit from 'uikit'
import Icons from 'uikit/dist/js/uikit-icons'

// Load UIkit icons
UIkit.use(Icons)

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
