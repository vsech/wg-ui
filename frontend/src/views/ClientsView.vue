<template>
  <div class="uk-section">
    <div class="uk-container">
      <div class="uk-flex uk-flex-between uk-flex-middle uk-margin-bottom">
        <h1 class="uk-heading-small">
          <span uk-icon="users"></span>
          WireGuard Clients
        </h1>
        <button class="uk-button uk-button-primary" @click="showCreateModal = true">
          <span uk-icon="plus"></span>
          Add Client
        </button>
      </div>

      <div v-if="clientsStore.error" class="uk-alert-danger uk-margin" uk-alert>
        <a class="uk-alert-close" uk-close></a>
        <p>{{ clientsStore.error }}</p>
      </div>

      <div v-if="clientsStore.listLoading && !clients.length" class="uk-text-center uk-margin-large">
        <div uk-spinner="ratio: 2"></div>
        <p class="uk-margin-top">Loading clients...</p>
      </div>

      <div
        v-else-if="!clients.length && !clientsStore.listLoading"
        class="uk-text-center uk-margin-large"
      >
        <span uk-icon="icon: users; ratio: 4" class="uk-text-muted"></span>
        <h3 class="uk-text-muted">No clients found</h3>
        <p class="uk-text-muted">Create your first WireGuard client to get started</p>
        <button class="uk-button uk-button-primary uk-margin-top" @click="showCreateModal = true">
          <span uk-icon="plus"></span>
          Add First Client
        </button>
      </div>

      <div v-else class="uk-grid-match uk-child-width-1-2@s uk-child-width-1-3@m" uk-grid>
        <div v-for="client in clients" :key="client.id">
          <div class="uk-card uk-card-default uk-card-hover">
            <div class="uk-card-header">
              <div class="uk-grid-small uk-flex-middle" uk-grid>
                <div class="uk-width-expand">
                  <h3 class="uk-card-title uk-margin-remove-bottom">
                    <span uk-icon="user"></span>
                    {{ client.name }}
                  </h3>
                  <p class="uk-text-meta uk-margin-remove-top">IP: {{ client.ip_address }}</p>
                </div>
                <div class="uk-width-auto">
                  <span
                    :class="client.is_active ? 'uk-label-success' : 'uk-label-warning'"
                    class="uk-label"
                  >
                    {{ client.is_active ? "Active" : "Inactive" }}
                  </span>
                </div>
              </div>
            </div>
            <div class="uk-card-body">
              <p class="uk-text-small uk-text-muted">
                Created: {{ formatDate(client.created_at) }}
              </p>
              <div class="uk-margin-small-top uk-text-small">
                <div>
                  <span class="uk-text-muted">Last handshake:</span>
                  <span>{{ formatDateTime(client.last_handshake) }}</span>
                </div>
                <div class="uk-margin-small-top">
                  <span class="uk-text-muted">Traffic:</span>
                  <span>
                    ↓ {{ formatBytes(client.bytes_received) }}
                    · ↑ {{ formatBytes(client.bytes_sent) }}
                  </span>
                </div>
              </div>
            </div>
            <div class="uk-card-footer">
              <div class="uk-button-group uk-width-1-1">
                <button
                  class="uk-button uk-button-default uk-width-1-2"
                  @click="showQRCode(client.name)"
                  :disabled="clientsStore.isDetailsLoading(client.name)"
                >
                  <span
                    v-if="clientsStore.isDetailsLoading(client.name)"
                    uk-spinner="ratio: 0.6"
                  ></span>
                  <span v-else uk-icon="camera"></span>
                  Details
                </button>
                <button
                  class="uk-button uk-button-danger uk-width-1-2"
                  @click="confirmDelete(client.name)"
                  :disabled="clientsStore.isDeleting(client.name)"
                >
                  <span v-if="clientsStore.isDeleting(client.name)" uk-spinner="ratio: 0.6"></span>
                  <span v-else uk-icon="trash"></span>
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <CreateClientModal v-model="showCreateModal" @client-created="onClientCreated" />

    <QRCodeModal
      v-model="showQRModal"
      :client-name="selectedClient"
      :client-details="selectedClientDetails"
      :loading="selectedClientLoading"
    />

    <div
      v-if="showDeleteModal"
      class="uk-flex-top"
      uk-modal
      :class="{ 'uk-open': showDeleteModal }"
    >
      <div class="uk-modal-dialog uk-modal-body uk-margin-auto-vertical">
        <button
          class="uk-modal-close-default"
          type="button"
          uk-close
          @click="showDeleteModal = false"
        ></button>
        <h2 class="uk-modal-title">Confirm Deletion</h2>
        <p>
          Are you sure you want to delete client <strong>{{ clientToDelete }}</strong
          >?
        </p>
        <p class="uk-text-warning">This action cannot be undone.</p>
        <p class="uk-text-right">
          <button
            class="uk-button uk-button-default uk-modal-close"
            @click="showDeleteModal = false"
          >
            Cancel
          </button>
          <button class="uk-button uk-button-danger" @click="deleteClient">Delete</button>
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, ref } from "vue";
import UIkit from "uikit";
import CreateClientModal from "@/components/CreateClientModal.vue";
import QRCodeModal from "@/components/QRCodeModal.vue";
import { useFormatters } from "@/composables/useFormatters";
import { useClientsStore } from "@/stores/clients";

export default {
  name: "ClientsView",
  components: {
    CreateClientModal,
    QRCodeModal,
  },
  setup() {
    const clientsStore = useClientsStore();
    const { formatDate, formatDateTime, formatBytes } = useFormatters();

    const showCreateModal = ref(false);
    const showQRModal = ref(false);
    const showDeleteModal = ref(false);
    const selectedClient = ref("");
    const clientToDelete = ref("");

    const clients = computed(() => clientsStore.clients);
    const selectedClientDetails = computed(
      () => clientsStore.clientDetails[selectedClient.value] || null
    );
    const selectedClientLoading = computed(
      () => !!selectedClient.value && clientsStore.isDetailsLoading(selectedClient.value)
    );

    const showQRCode = async (clientName) => {
      selectedClient.value = clientName;
      showQRModal.value = true;
      try {
        await clientsStore.fetchClientDetails(clientName);
      } catch {
        UIkit.notification("Failed to load client details", "danger");
      }
    };

    const confirmDelete = (clientName) => {
      clientToDelete.value = clientName;
      showDeleteModal.value = true;
    };

    const deleteClient = async () => {
      const success = await clientsStore.deleteClient(clientToDelete.value);
      if (success) {
        UIkit.notification(`Client ${clientToDelete.value} deleted successfully`, "success");
      } else {
        UIkit.notification("Failed to delete client", "danger");
      }
      showDeleteModal.value = false;
      clientToDelete.value = "";
    };

    const onClientCreated = (clientData) => {
      UIkit.notification(`Client ${clientData.name} created successfully`, "success");
      showCreateModal.value = false;
      selectedClient.value = clientData.name;
    };

    onMounted(() => {
      clientsStore.fetchClients();
    });

    return {
      clientsStore,
      clients,
      showCreateModal,
      showQRModal,
      showDeleteModal,
      selectedClient,
      clientToDelete,
      selectedClientDetails,
      selectedClientLoading,
      formatDate,
      formatDateTime,
      formatBytes,
      showQRCode,
      confirmDelete,
      deleteClient,
      onClientCreated,
    };
  },
};
</script>

<style scoped>
.uk-modal.uk-open {
  display: block;
}
</style>
