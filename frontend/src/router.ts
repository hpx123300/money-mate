import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";

import LoginView from "./views/LoginView.vue";
import AppLayout from "./components/AppLayout.vue";
import DashboardView from "./views/DashboardView.vue";
import TransactionsView from "./views/TransactionsView.vue";
import BudgetView from "./views/BudgetView.vue";
import CategoriesView from "./views/CategoriesView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView },
    {
      path: "/",
      component: AppLayout,
      redirect: "/dashboard",
      children: [
        { path: "dashboard", component: DashboardView, meta: { requiresAuth: true } },
        { path: "transactions", component: TransactionsView, meta: { requiresAuth: true } },
        { path: "budget", component: BudgetView, meta: { requiresAuth: true } },
        { path: "categories", component: CategoriesView, meta: { requiresAuth: true } },
      ],
    },
  ],
});

// 路由守卫：没登录不能进业务页面
router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.token) {
    return "/login";
  }
  if (to.path === "/login" && auth.token) {
    return "/dashboard";
  }
});

export default router;
