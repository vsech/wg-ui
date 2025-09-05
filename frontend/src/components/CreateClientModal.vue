<template>
  <div v-if="modelValue" class="uk-flex-top" uk-modal :class="{ 'uk-open': modelValue }">
    <div class="uk-modal-dialog uk-modal-body uk-margin-auto-vertical">
      <button class="uk-modal-close-default" type="button" uk-close @click="closeModal"></button>
      <h2 class="uk-modal-title">
        <span uk-icon="plus-circle"></span>
        Create New Client
      </h2>

      <form @submit.prevent="handleSubmit" class="uk-form-stacked">
        <div class="uk-margin">
          <label class="uk-form-label" for="client-name">Client Name</label>
          <div class="uk-form-controls">
            <input
              class="uk-input"
              id="client-name"
              type="text"
              v-model="form.name"
              placeholder="Enter client name (e.g., laptop, phone)"
              required
              :disabled="loading"
            />
            <div class="uk-text-meta uk-margin-small-top">
              Only letters, numbers, hyphens and underscores allowed
            </div>
          </div>
        </div>

        <div class="uk-margin">
          <label class="uk-form-label" for="dns-servers">DNS Servers</label>
          <div class="uk-form-controls">
            <select class="uk-select" id="dns-servers" v-model="form.dns" :disabled="loading">
              <option value="8.8.8.8, 8.8.4.4">Google DNS (8.8.8.8, 8.8.4.4)</option>
              <option value="1.1.1.1, 1.0.0.1">Cloudflare DNS (1.1.1.1, 1.0.0.1)</option>
              <option value="208.67.222.222, 208.67.220.220">
                OpenDNS (208.67.222.222, 208.67.220.220)
              </option>
              <option value="9.9.9.9, 149.112.112.112">Quad9 DNS (9.9.9.9, 149.112.112.112)</option>
              <option value="94.140.14.14, 94.140.15.15">
                AdGuard DNS (94.140.14.14, 94.140.15.15)
              </option>
            </select>
          </div>
        </div>

        <div v-if="error" class="uk-alert-danger uk-margin" uk-alert>
          <p>{{ error }}</p>
        </div>

        <div class="uk-margin uk-text-right">
          <button
            class="uk-button uk-button-default uk-margin-small-right"
            type="button"
            @click="closeModal"
            :disabled="loading"
          >
            Cancel
          </button>
          <button
            class="uk-button uk-button-primary"
            type="submit"
            :disabled="loading || !form.name.trim()"
          >
            <span v-if="loading" uk-spinner="ratio: 0.8"></span>
            <span v-else>Create Client</span>
          </button>
        </div>
      </form>

      <!-- Success State with QR Code -->
      <div v-if="createdClient" class="uk-margin-top uk-padding uk-background-muted">
        <h3 class="uk-text-success">
          <span uk-icon="check-circle"></span>
          Client Created Successfully!
        </h3>
        <p><strong>Name:</strong> {{ createdClient.name }}</p>

        <div class="uk-text-center uk-margin">
          <img
            :src="createdClient.qr_code"
            alt="QR Code"
            class="uk-border-rounded"
            style="max-width: 200px"
          />
          <p class="uk-text-small uk-text-muted uk-margin-small-top">
            Scan this QR code with your WireGuard app
          </p>
        </div>

        <div class="uk-margin">
          <label class="uk-form-label">Configuration File:</label>
          <textarea
            class="uk-textarea uk-text-small"
            :value="createdClient.config"
            readonly
            rows="8"
          ></textarea>
        </div>

        <div class="uk-text-right">
          <button class="uk-button uk-button-primary" @click="downloadConfig">
            <span uk-icon="download"></span>
            Download Config
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch } from "vue";
import { useClientsStore } from "@/stores/clients";

export default {
  name: "CreateClientModal",
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["update:modelValue", "client-created"],
  setup(props, { emit }) {
    const clientsStore = useClientsStore();

    const form = ref({
      name: "",
      dns: "8.8.8.8, 8.8.4.4",
    });

    const loading = ref(false);
    const error = ref("");
    const createdClient = ref(null);

    const closeModal = () => {
      emit("update:modelValue", false);
      resetForm();
    };

    const resetForm = () => {
      form.value = {
        name: "",
        dns: "8.8.8.8, 8.8.4.4",
      };
      error.value = "";
      createdClient.value = null;
      loading.value = false;
    };

    const handleSubmit = async () => {
      loading.value = true;
      error.value = "";

      try {
        // Sanitize client name
        const sanitizedName = form.value.name.replace(/[^a-zA-Z0-9_-]/g, "_").substring(0, 15);

        const clientData = {
          name: sanitizedName,
          dns: form.value.dns,
        };

        const response = await clientsStore.createClient(clientData);
        createdClient.value = response;
        emit("client-created", response);
      } catch (err) {
        error.value = err.response?.data?.detail || "Failed to create client";
      } finally {
        loading.value = false;
      }
    };

    const downloadConfig = () => {
      if (!createdClient.value) return;

      const blob = new Blob([createdClient.value.config], { type: "text/plain" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${createdClient.value.name}.conf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    };

    // Reset form when modal closes
    watch(
      () => props.modelValue,
      (newValue) => {
        if (!newValue) {
          resetForm();
        }
      }
    );

    return {
      form,
      loading,
      error,
      createdClient,
      closeModal,
      handleSubmit,
      downloadConfig,
    };
  },
};
</script>

<style scoped>
.uk-modal.uk-open {
  display: block;
}
</style>
