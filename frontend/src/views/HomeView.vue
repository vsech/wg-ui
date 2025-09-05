<template>
  <div class="uk-section uk-section-muted">
    <div class="uk-container">
      <div class="uk-text-center">
        <h1 class="uk-heading-primary">
          <span uk-icon="icon: settings; ratio: 3"></span>
          WireGuard Client Manager
        </h1>
        <p class="uk-text-lead">Manage your WireGuard VPN clients with ease</p>

        <div class="uk-margin-large-top">
          <router-link to="/clients" class="uk-button uk-button-primary uk-button-large">
            <span uk-icon="users"></span>
            Manage Clients
          </router-link>
        </div>
      </div>

      <div class="uk-grid-match uk-child-width-1-3@m uk-margin-large-top" uk-grid>
        <div>
          <div class="uk-card uk-card-default uk-card-body uk-text-center">
            <span uk-icon="icon: plus-circle; ratio: 2" class="uk-text-primary"></span>
            <h3 class="uk-card-title">Create Clients</h3>
            <p>Add new WireGuard clients with custom DNS settings</p>
          </div>
        </div>
        <div>
          <div class="uk-card uk-card-default uk-card-body uk-text-center">
            <span uk-icon="icon: list; ratio: 2" class="uk-text-success"></span>
            <h3 class="uk-card-title">Manage Clients</h3>
            <p>View, edit, and delete existing WireGuard clients</p>
          </div>
        </div>
        <div>
          <div class="uk-card uk-card-default uk-card-body uk-text-center">
            <span uk-icon="icon: camera; ratio: 2" class="uk-text-warning"></span>
            <h3 class="uk-card-title">QR Codes</h3>
            <p>Generate QR codes for easy mobile device setup</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "HomeView",
};
</script>
