import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/chat/ChatView.vue'
import AdminLayout from '../views/admin/AdminLayout.vue'
import SourcesView from '../views/admin/SourcesView.vue'
import TasksView from '../views/admin/TasksView.vue'
import KnowledgeView from '../views/admin/KnowledgeView.vue'
import StatsView from '../views/admin/StatsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: ChatView },
    {
      path: '/admin',
      component: AdminLayout,
      redirect: '/admin/sources',
      children: [
        { path: 'sources', component: SourcesView },
        { path: 'tasks', component: TasksView },
        { path: 'knowledge', component: KnowledgeView },
        { path: 'stats', component: StatsView },
      ],
    },
  ],
})

export default router
