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

      <div v-else-if="qrCode" class="uk-text-center">
        <div class="uk-margin">
          <img :src="qrCode" alt="WireGuard QR Code" class="uk-border-rounded qr-code-image" />
        </div>

        <div class="uk-margin">
          <p class="uk-text-lead">Scan with WireGuard App</p>
          <p class="uk-text-small uk-text-muted">
            Open the WireGuard app on your device and tap the "+" button, then select "Create from
            QR code"
          </p>
        </div>

        <div class="uk-margin uk-text-center">
          <button class="uk-button uk-button-primary uk-margin-small-right" @click="downloadQR">
            <span uk-icon="download"></span>
            Download QR Code
          </button>
          <button class="uk-button uk-button-default" @click="copyToClipboard">
            <span uk-icon="copy"></span>
            Copy Config
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

    const closeModal = () => {
      emit("update:modelValue", false);
    };

    const downloadQR = () => {
      if (!props.qrCode) return;

      // Convert base64 to blob
      const base64Data = props.qrCode.replace(/^data:image\/png;base64,/, "");
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

    const copyToClipboard = async () => {
      try {
        // Get the config text from the store
        const client = clientsStore.clients.find((c) => c.name === props.clientName);
        if (client && client.config) {
          await navigator.clipboard.writeText(client.config);
          UIkit.notification("Configuration copied to clipboard", "success");
        } else {
          // Fallback: fetch config if not available
          const response = await clientsStore.getClientConfig(props.clientName);
          await navigator.clipboard.writeText(response.config);
          UIkit.notification("Configuration copied to clipboard", "success");
        }
      } catch (err) {
        UIkit.notification("Failed to copy to clipboard", "danger");
      }
    };

    return {
      loading,
      error,
      closeModal,
      downloadQR,
      copyToClipboard,
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
