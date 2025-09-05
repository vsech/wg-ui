<template>
  <div id="app">
    <nav class="uk-navbar-container" uk-navbar>
      <div class="uk-navbar-left">
        <a class="uk-navbar-item uk-logo" href="#" @click="$router.push('/')">
          <span uk-icon="icon: settings; ratio: 1.5"></span>
          WireGuard Manager
        </a>
      </div>
      <div class="uk-navbar-right" v-if="authStore.isAuthenticated">
        <ul class="uk-navbar-nav">
          <li>
            <a @click="$router.push('/clients')">
              <span uk-icon="users"></span>
              Clients
            </a>
          </li>
          <li>
            <a @click="logout">
              <span uk-icon="sign-out"></span>
              Logout
            </a>
          </li>
        </ul>
      </div>
    </nav>

    <div class="uk-container uk-container-expand uk-margin-top">
      <router-view />
    </div>

    <!-- Loading overlay -->
    <div v-if="loading" class="uk-overlay-default uk-position-cover uk-flex uk-flex-center uk-flex-middle">
      <div uk-spinner="ratio: 2"></div>
    </div>
  </div>
</template>

<script>
import { useAuthStore } from '@/stores/auth'
import { computed } from 'vue'

export default {
  name: 'App',
  setup() {
    const authStore = useAuthStore()
    
    const loading = computed(() => authStore.loading)

    const logout = async () => {
      await authStore.logout()
    }

    return {
      authStore,
      loading,
      logout
    }
  }
}
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

#app {
  min-height: 100vh;
  position: relative;
}

.uk-navbar-container {
  background: #1e87f0;
}

.uk-navbar-nav > li > a {
  color: white !important;
  text-transform: none;
}

.uk-navbar-nav > li > a:hover {
  color: #f0f9ff !important;
}

.uk-logo {
  color: white !important;
  font-weight: bold;
}
</style>
