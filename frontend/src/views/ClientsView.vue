<template>
  <div class="uk-section">
    <div class="uk-container">
      <div class="uk-flex uk-flex-between uk-flex-middle uk-margin-bottom">
        <h1 class="uk-heading-small">
          <span uk-icon="users"></span>
          WireGuard Clients
        </h1>
        <button 
          class="uk-button uk-button-primary" 
          @click="showCreateModal = true"
        >
          <span uk-icon="plus"></span>
          Add Client
        </button>
      </div>

      <!-- Error Alert -->
      <div v-if="clientsStore.error" class="uk-alert-danger uk-margin" uk-alert>
        <a class="uk-alert-close" uk-close></a>
        <p>{{ clientsStore.error }}</p>
      </div>

      <!-- Loading State -->
      <div v-if="clientsStore.loading && !clients.length" class="uk-text-center uk-margin-large">
        <div uk-spinner="ratio: 2"></div>
        <p class="uk-margin-top">Loading clients...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="!clients.length && !clientsStore.loading" class="uk-text-center uk-margin-large">
        <span uk-icon="icon: users; ratio: 4" class="uk-text-muted"></span>
        <h3 class="uk-text-muted">No clients found</h3>
        <p class="uk-text-muted">Create your first WireGuard client to get started</p>
        <button 
          class="uk-button uk-button-primary uk-margin-top" 
          @click="showCreateModal = true"
        >
          <span uk-icon="plus"></span>
          Add First Client
        </button>
      </div>

      <!-- Clients Grid -->
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
                  <p class="uk-text-meta uk-margin-remove-top">
                    IP: {{ client.ip_address }}
                  </p>
                </div>
                <div class="uk-width-auto">
                  <span 
                    :class="client.is_active ? 'uk-label-success' : 'uk-label-warning'" 
                    class="uk-label"
                  >
                    {{ client.is_active ? 'Active' : 'Inactive' }}
                  </span>
                </div>
              </div>
            </div>
            <div class="uk-card-body">
              <p class="uk-text-small uk-text-muted">
                Created: {{ formatDate(client.created_at) }}
              </p>
            </div>
            <div class="uk-card-footer">
              <div class="uk-button-group uk-width-1-1">
                <button 
                  class="uk-button uk-button-default uk-width-1-2"
                  @click="showQRCode(client.name)"
                >
                  <span uk-icon="camera"></span>
                  QR Code
                </button>
                <button 
                  class="uk-button uk-button-danger uk-width-1-2"
                  @click="confirmDelete(client.name)"
                >
                  <span uk-icon="trash"></span>
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Client Modal -->
    <CreateClientModal 
      v-model="showCreateModal" 
      @client-created="onClientCreated"
    />

    <!-- QR Code Modal -->
    <QRCodeModal 
      v-model="showQRModal" 
      :client-name="selectedClient"
      :qr-code="qrCodeData"
    />

    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteModal" class="uk-flex-top" uk-modal :class="{ 'uk-open': showDeleteModal }">
      <div class="uk-modal-dialog uk-modal-body uk-margin-auto-vertical">
        <button class="uk-modal-close-default" type="button" uk-close @click="showDeleteModal = false"></button>
        <h2 class="uk-modal-title">Confirm Deletion</h2>
        <p>Are you sure you want to delete client <strong>{{ clientToDelete }}</strong>?</p>
        <p class="uk-text-warning">This action cannot be undone.</p>
        <p class="uk-text-right">
          <button class="uk-button uk-button-default uk-modal-close" @click="showDeleteModal = false">Cancel</button>
          <button class="uk-button uk-button-danger" @click="deleteClient">Delete</button>
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useClientsStore } from '@/stores/clients'
import CreateClientModal from '@/components/CreateClientModal.vue'
import QRCodeModal from '@/components/QRCodeModal.vue'
import UIkit from 'uikit'

export default {
  name: 'ClientsView',
  components: {
    CreateClientModal,
    QRCodeModal
  },
  setup() {
    const clientsStore = useClientsStore()
    
    const showCreateModal = ref(false)
    const showQRModal = ref(false)
    const showDeleteModal = ref(false)
    const selectedClient = ref('')
    const clientToDelete = ref('')
    const qrCodeData = ref('')

    const clients = computed(() => clientsStore.clients)

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleDateString()
    }

    const showQRCode = async (clientName) => {
      try {
        selectedClient.value = clientName
        qrCodeData.value = await clientsStore.getClientQR(clientName)
        showQRModal.value = true
      } catch (error) {
        UIkit.notification('Failed to generate QR code', 'danger')
      }
    }

    const confirmDelete = (clientName) => {
      clientToDelete.value = clientName
      showDeleteModal.value = true
    }

    const deleteClient = async () => {
      const success = await clientsStore.deleteClient(clientToDelete.value)
      if (success) {
        UIkit.notification(`Client ${clientToDelete.value} deleted successfully`, 'success')
      } else {
        UIkit.notification('Failed to delete client', 'danger')
      }
      showDeleteModal.value = false
      clientToDelete.value = ''
    }

    const onClientCreated = (clientData) => {
      UIkit.notification(`Client ${clientData.name} created successfully`, 'success')
      showCreateModal.value = false
    }

    onMounted(() => {
      clientsStore.fetchClients()
    })

    return {
      clientsStore,
      clients,
      showCreateModal,
      showQRModal,
      showDeleteModal,
      selectedClient,
      clientToDelete,
      qrCodeData,
      formatDate,
      showQRCode,
      confirmDelete,
      deleteClient,
      onClientCreated
    }
  }
}
</script>

<style scoped>
.uk-modal.uk-open {
  display: block;
}
</style>
