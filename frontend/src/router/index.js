import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Wallets from '../views/Wallets.vue'
import WalletDetail from '../views/WalletDetail.vue'
import Nodes from '../views/Nodes.vue'
import Statistics from '../views/Statistics.vue'
import Settings from '../views/Settings.vue'
import Assets from '../views/Assets.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/wallets', component: Wallets },
    { path: '/wallets/:id', component: WalletDetail, props: true },
    { path: '/nodes', component: Nodes },
    { path: '/stats', component: Statistics },
    { path: '/settings', component: Settings },
    { path: '/assets', component: Assets },
  ],
})
