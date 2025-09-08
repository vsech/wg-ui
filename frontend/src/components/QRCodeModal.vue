<template>
  <div v-if="modelValue" class="uk-flex-top" uk-modal :class="{ 'uk-open': modelValue }">
    <div class="uk-modal-dialog uk-modal-body uk-margin-auto-vertical">
      <button class="uk-modal-close-default" type="button" uk-close @click="closeModal"></button>
      <h2 class="uk-modal-title">
        <span uk-icon="camera"></span>
        QR Code for {{ clientName }}
      </h2>

      <div v-if="loading" class="uk-text-center uk-margin-large">
        <div uk-spinner="ratio: 2"></div>
        <p class="uk-margin-top">Generating QR code...</p>
      </div>

      <div v-else-if="error" class="uk-alert-danger" uk-alert>
        <p>{{ error }}</p>
      </div>

      <div v-else-if="displayedQR" class="uk-text-center">
        <div class="uk-margin">
          <img :src="displayedQR" alt="WireGuard QR Code" class="uk-border-rounded qr-code-image" />
        </div>

        <div class="uk-margin">
          <p class="uk-text-lead">Scan with WireGuard App</p>
          <p class="uk-text-small uk-text-muted">
            Open the WireGuard app on your device and tap the "+" button, then select "Create from
            QR code"
          </p>
        </div>

        <!-- Stats -->
        <div class="uk-margin uk-text-center uk-text-small">
          <div>
            <span class="uk-text-muted">Last handshake:</span>
            <span>{{ formatDateTime(stats.last_handshake) }}</span>
          </div>
          <div class="uk-margin-small-top">
            <span class="uk-text-muted">Traffic:</span>
            <span>
              ↓ {{ formatBytes(stats.bytes_received) }} · ↑ {{ formatBytes(stats.bytes_sent) }}
            </span>
          </div>
        </div>

        <div class="uk-margin uk-text-center">
          <button class="uk-button uk-button-primary uk-margin-small-right" @click="downloadQR">
            <span uk-icon="download"></span>
            Download QR Code
          </button>
          <button class="uk-button uk-button-default" @click="downloadConfig">
            <span uk-icon="download"></span>
            Download Config
          </button>
        </div>

        <!-- Instructions -->
        <div class="uk-margin-top uk-padding uk-background-muted uk-border-rounded">
          <h4 class="uk-text-bold">Setup Instructions:</h4>
          <ol class="uk-text-small">
            <li>Install WireGuard app on your device</li>
            <li>Open the app and tap "Add Tunnel"</li>
            <li>Select "Create from QR code"</li>
            <li>Scan the QR code above</li>
            <li>Give the tunnel a name and save</li>
            <li>Toggle the connection to connect</li>
          </ol>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch } from "vue";
import { useClientsStore } from "@/stores/clients";
import UIkit from "uikit";

export default {
  name: "QRCodeModal",
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
    clientName: {
      type: String,
      default: "",
    },
    qrCode: {
      type: String,
      default: "",
    },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const clientsStore = useClientsStore();
    const loading = ref(false);
    const error = ref("");
    const configText = ref("");
    const displayedQR = ref("");
    const stats = ref({ last_handshake: null, bytes_received: 0, bytes_sent: 0 });

    const closeModal = () => {
      emit("update:modelValue", false);
    };

    const downloadQR = () => {
      if (!displayedQR.value) return;

      // Convert base64 to blob
      const base64Data = displayedQR.value.replace(/^data:image\/png;base64,/, "");
      const byteCharacters = atob(base64Data);
      const byteNumbers = new Array(byteCharacters.length);

      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }

      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: "image/png" });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${props.clientName}-qr.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      UIkit.notification("QR code downloaded successfully", "success");
    };

    const downloadConfig = async () => {
      try {
        let configContent = "";
        
        // Get the config text from the store
        const client = clientsStore.clients.find((c) => c.name === props.clientName);
        if (client && client.config) {
          configContent = client.config;
        } else {
          // Fallback: fetch config if not available
          const response = await clientsStore.getClientConfig(props.clientName);
          configContent = response.config;
        }

        // Create blob and download
        const blob = new Blob([configContent], { type: "text/plain" });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${props.clientName}.conf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        UIkit.notification("Configuration downloaded successfully", "success");
      } catch (err) {
        UIkit.notification("Failed to download configuration", "danger");
      }
    };

    // Helpers
    const formatDateTime = (dateTimeString) => {
      if (!dateTimeString) return "Never";
      try {
        const dt = new Date(dateTimeString);
        if (isNaN(dt.getTime())) return "Never";
        return dt.toLocaleString();
      } catch {
        return "Never";
      }
    };

    const formatBytes = (bytes) => {
      if (!bytes || bytes <= 0) return "0 B";
      const units = ["B", "KB", "MB", "GB", "TB"]; 
      let i = 0;
      let val = bytes;
      while (val >= 1024 && i < units.length - 1) {
        val /= 1024;
        i++;
      }
      return `${val.toFixed(val < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
    };

    // Load stats and config when modal opens
    watch(() => props.modelValue, async (open) => {
      if (!open) return;
      try {
        loading.value = true;
        // Prefer passed QR initially
        displayedQR.value = props.qrCode || "";
        const full = await clientsStore.getClientConfig(props.clientName);
        // Update stats and prefer server QR if provided
        stats.value.last_handshake = full.last_handshake;
        stats.value.bytes_received = full.bytes_received;
        stats.value.bytes_sent = full.bytes_sent;
        if (full.qr_code) {
          displayedQR.value = full.qr_code;
        }
      } catch (e) {
        // non-fatal, just notify
        UIkit.notification("Failed to load client details", "warning");
      } finally {
        loading.value = false;
      }
    }, { immediate: true });

    return {
      loading,
      error,
      closeModal,
      downloadQR,
      downloadConfig,
      displayedQR,
      stats,
      formatDateTime,
      formatBytes,
    };
  },
};
</script>

<style scoped>
.uk-modal.uk-open {
  display: block;
}

.qr-code-image {
  max-width: 300px;
  width: 100%;
  height: auto;
  background: white;
  padding: 10px;
}
</style>
