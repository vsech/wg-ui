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
        <p class="uk-margin-top">Loading client details...</p>
      </div>

      <div v-else-if="clientDetails?.qr_code" class="uk-text-center">
        <div class="uk-margin">
          <img
            :src="clientDetails.qr_code"
            alt="WireGuard QR Code"
            class="uk-border-rounded qr-code-image"
          />
        </div>

        <div class="uk-margin">
          <p class="uk-text-lead">Scan with WireGuard App</p>
          <p class="uk-text-small uk-text-muted">
            Open the WireGuard app on your device and tap the "+" button, then select "Create from
            QR code"
          </p>
        </div>

        <div class="uk-margin uk-text-center uk-text-small">
          <div>
            <span class="uk-text-muted">Last handshake:</span>
            <span>{{ formatDateTime(clientDetails.last_handshake) }}</span>
          </div>
          <div class="uk-margin-small-top">
            <span class="uk-text-muted">Traffic:</span>
            <span>
              ↓ {{ formatBytes(clientDetails.bytes_received) }} · ↑
              {{ formatBytes(clientDetails.bytes_sent) }}
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

      <div v-else class="uk-alert-warning" uk-alert>
        <p>Client details are not available.</p>
      </div>
    </div>
  </div>
</template>

<script>
import UIkit from "uikit";
import { useDownloads } from "@/composables/useDownloads";
import { useFormatters } from "@/composables/useFormatters";

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
    clientDetails: {
      type: Object,
      default: () => null,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const { downloadDataUrl, downloadTextFile } = useDownloads();
    const { formatDateTime, formatBytes } = useFormatters();

    const closeModal = () => {
      emit("update:modelValue", false);
    };

    const downloadQR = () => {
      if (!props.clientDetails?.qr_code) return;
      downloadDataUrl(props.clientDetails.qr_code, `${props.clientName}-qr.png`, "image/png");
      UIkit.notification("QR code downloaded successfully", "success");
    };

    const downloadConfig = () => {
      if (!props.clientDetails?.config) return;
      downloadTextFile(props.clientDetails.config, `${props.clientName}.conf`);
      UIkit.notification("Configuration downloaded successfully", "success");
    };

    return {
      closeModal,
      downloadQR,
      downloadConfig,
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
