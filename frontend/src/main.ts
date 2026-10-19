import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus, { ElMessage } from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";

import App from "./App.vue";
import router from "./router";
import { setErrorNotifier } from "./api";
import "./styles.css";

// 把 UI 层的气泡接到 api 层：网络超时 / 5xx 由拦截器统一提示，业务代码不用每处写一遍
setErrorNotifier((message) => ElMessage.error(message));

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(ElementPlus, { locale: zhCn });
app.mount("#app");

