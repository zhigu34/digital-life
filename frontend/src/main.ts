import { createApp } from "vue";
import App from "./App.vue";
import "./styles.css";
import "./features/shows/shows.css";
createApp(App).mount("#app");
if ("serviceWorker" in navigator && import.meta.env.PROD)
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("/sw.js").catch(() => {}),
  );
