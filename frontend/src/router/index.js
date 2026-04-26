import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Wallets from '../views/Wallets.vue'
import WalletDetail from '../views/WalletDetail.vue'
import Nodes from '../views/Nodes.vue'
import Statistics from '../views/Statistics.vue'
import Settings from '../views/Settings.vue'
import Assets from '../views/Assets.vue'
import Tax from '../views/Tax.vue'
import Support from '../views/Support.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/wallets', component: Wallets },
    { path: '/wallets/:id', component: WalletDetail, props: true },
    { path: '/nodes', component: Nodes },
    { path: '/stats', component: Statistics },
    { path: '/tax', component: Tax },
    { path: '/settings', component: Settings },
    { path: '/assets', component: Assets },
    { path: '/support', component: Support },
  ],
})
