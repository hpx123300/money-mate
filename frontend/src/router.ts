import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";

import LoginView from "./views/LoginView.vue";
import AppLayout from "./components/AppLayout.vue";

// 页面按路由懒加载：登录后只下载当前页的代码，年度报告这类低频页不占首屏体积
const DashboardView = () => import("./views/DashboardView.vue");
const TransactionsView = () => import("./views/TransactionsView.vue");
const BudgetView = () => import("./views/BudgetView.vue");
const CategoriesView = () => import("./views/CategoriesView.vue");
const AnnualReportView = () => import("./views/AnnualReportView.vue");

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
        { path: "report", component: AnnualReportView, meta: { requiresAuth: true } },
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
