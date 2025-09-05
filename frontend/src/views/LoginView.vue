<template>
  <div class="uk-section uk-section-muted uk-flex uk-flex-center uk-flex-middle" style="min-height: 100vh;">
    <div class="uk-width-1-3@m uk-width-1-2@s">
      <div class="uk-card uk-card-default uk-card-body">
        <h3 class="uk-card-title uk-text-center">
          <span uk-icon="icon: lock; ratio: 1.5"></span>
          Login to WireGuard Manager
        </h3>

        <form @submit.prevent="handleLogin" class="uk-form-stacked">
          <div class="uk-margin">
            <label class="uk-form-label" for="username">Username</label>
            <div class="uk-form-controls">
              <input 
                class="uk-input" 
                id="username" 
                type="text" 
                v-model="form.username"
                placeholder="Enter your username"
                required
              >
            </div>
          </div>

          <div class="uk-margin">
            <label class="uk-form-label" for="password">Password</label>
            <div class="uk-form-controls">
              <input 
                class="uk-input" 
                id="password" 
                type="password" 
                v-model="form.password"
                placeholder="Enter your password"
                required
              >
            </div>
          </div>

          <div v-if="authStore.error" class="uk-alert-danger" uk-alert>
            <a class="uk-alert-close" uk-close></a>
            <p>{{ authStore.error }}</p>
          </div>

          <div class="uk-margin">
            <button 
              class="uk-button uk-button-primary uk-width-1-1" 
              type="submit"
              :disabled="authStore.loading"
            >
              <span v-if="authStore.loading" uk-spinner="ratio: 0.8"></span>
              <span v-else>Login</span>
            </button>
          </div>
        </form>

        <div class="uk-text-center uk-margin-top">
          <p class="uk-text-muted">
            Don't have an account? 
            <a @click="showRegister = !showRegister" class="uk-link">Register here</a>
          </p>
        </div>

        <!-- Registration Form -->
        <div v-if="showRegister" class="uk-margin-top uk-padding-small uk-background-muted">
          <h4>Create Account</h4>
          <form @submit.prevent="handleRegister" class="uk-form-stacked">
            <div class="uk-margin">
              <label class="uk-form-label" for="reg-username">Username</label>
              <div class="uk-form-controls">
                <input 
                  class="uk-input" 
                  id="reg-username" 
                  type="text" 
                  v-model="registerForm.username"
                  placeholder="Choose a username"
                  required
                >
              </div>
            </div>

            <div class="uk-margin">
              <label class="uk-form-label" for="reg-password">Password</label>
              <div class="uk-form-controls">
                <input 
                  class="uk-input" 
                  id="reg-password" 
                  type="password" 
                  v-model="registerForm.password"
                  placeholder="Choose a password"
                  required
                >
              </div>
            </div>

            <div class="uk-margin">
              <button 
                class="uk-button uk-button-secondary uk-width-1-1" 
                type="submit"
                :disabled="authStore.loading"
              >
                <span v-if="authStore.loading" uk-spinner="ratio: 0.8"></span>
                <span v-else>Register</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import UIkit from 'uikit'

export default {
  name: 'LoginView',
  setup() {
    const router = useRouter()
    const authStore = useAuthStore()
    
    const form = ref({
      username: '',
      password: ''
    })

    const registerForm = ref({
      username: '',
      password: ''
    })

    const showRegister = ref(false)

    const handleLogin = async () => {
      const success = await authStore.login(form.value)
      if (success) {
        router.push('/clients')
      }
    }

    const handleRegister = async () => {
      const success = await authStore.register(registerForm.value)
      if (success) {
        UIkit.notification('Account created successfully! Please login.', 'success')
        showRegister.value = false
        registerForm.value = { username: '', password: '' }
      }
    }

    return {
      form,
      registerForm,
      showRegister,
      authStore,
      handleLogin,
      handleRegister
    }
  }
}
</script>
