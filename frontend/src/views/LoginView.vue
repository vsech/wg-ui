<template>
  <div
    class="uk-section uk-section-muted uk-flex uk-flex-center uk-flex-middle"
    style="min-height: 100vh"
  >
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
              />
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
              />
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

      </div>
    </div>
  </div>
</template>

<script>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "LoginView",
  setup() {
    const router = useRouter();
    const authStore = useAuthStore();

    const form = ref({
      username: "",
      password: "",
    });


    const handleLogin = async () => {
      const success = await authStore.login(form.value);
      if (success) {
        router.push("/clients");
      }
    };


    return {
      form,
      authStore,
      handleLogin,
    };
  },
};
</script>
