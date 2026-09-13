/* Shared helpers: JWT-aware fetch wrapper, toasts, auth-aware nav. */
(function () {
  const ACCESS = "einvite_access";
  const REFRESH = "einvite_refresh";

  function store(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (_) { /* storage blocked */ }
  }
  function read(key) {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  }

  let refreshing = null;
  async function refreshAccess() {
    const refresh = read(REFRESH);
    if (!refresh) return false;
    refreshing = refreshing || fetch("/api/auth/token/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    }).then(async (res) => {
      if (!res.ok) return false;
      const data = await res.json();
      store(ACCESS, data.access);
      if (data.refresh) store(REFRESH, data.refresh);
      return true;
    }).catch(() => false).finally(() => { refreshing = null; });
    return refreshing;
  }

  const API = {
    isLoggedIn: () => Boolean(read(REFRESH)),

    setTokens({ access, refresh }) {
      store(ACCESS, access);
      store(REFRESH, refresh);
    },

    logout() {
      store(ACCESS, null);
      store(REFRESH, null);
      location.href = "/login/";
    },

    requireAuth() {
      if (!API.isLoggedIn()) {
        location.href = "/login/?next=" + encodeURIComponent(location.pathname + location.search);
        return false;
      }
      return true;
    },

    /* request("/invitations/", {method, json, form, raw}) */
    async request(path, { method = "GET", json, form, raw = false } = {}) {
      const send = () => {
        const headers = {};
        const token = read(ACCESS);
        if (token) headers.Authorization = "Bearer " + token;
        let body;
        if (json !== undefined) {
          headers["Content-Type"] = "application/json";
          body = JSON.stringify(json);
        } else if (form) {
          body = form;
        }
        return fetch("/api" + path, { method, headers, body });
      };

      let res = await send();
      if (res.status === 401 && read(REFRESH)) {
        if (await refreshAccess()) res = await send();
        else { API.logout(); throw new Error("Session expired. Please log in again."); }
      }
      if (raw && res.ok) return res;

      const data = res.status === 204 ? null : await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error((data && (data.error || data.detail)) || "Something went wrong. Please try again.");
        err.status = res.status;
        err.data = data || {};
        throw err;
      }
      return data;
    },
  };

  let toastTimer;
  function toast(message, type = "info") {
    const el = document.getElementById("toast");
    if (!el) return alert(message);
    el.textContent = message;
    el.className = "toast toast-" + type;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 4200);
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast("Link copied!", "success");
    } catch (_) {
      prompt("Copy this link:", text);
    }
  }

  function initNav() {
    const loggedIn = API.isLoggedIn();
    document.querySelectorAll("[data-auth]").forEach((el) => {
      el.hidden = (el.dataset.auth === "in") !== loggedIn;
    });
    document.querySelectorAll('[data-action="logout"]').forEach((el) =>
      el.addEventListener("click", API.logout));
  }

  window.API = API;
  window.toast = toast;
  window.escapeHtml = escapeHtml;
  window.copyText = copyText;
  document.addEventListener("DOMContentLoaded", initNav);
})();
