const { createApp, ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } = Vue;

const API = "/api";
const LOGIN_REQUIRED_ROUTES = ["publish", "orders", "points", "me", "admin"];

// 跨页面共享的最小状态；业务数据由各页面通过 API 加载。
const store = reactive({
  token: localStorage.getItem("cbc_token") || "",
  user: null,
  keyword: "",
  error: "",
  notice: "",
  loading: 0,
  route: { name: "home", params: {} },
});

function setError(msg) {
  store.error = msg;
  setTimeout(() => (store.error = ""), 4000);
}
function setNotice(msg) {
  store.notice = msg;
  setTimeout(() => (store.notice = ""), 3500);
}

async function apiRequest(path, { method = "GET", body } = {}, form = false) {
  const headers = form ? {} : { "Content-Type": "application/json" };
  if (store.token) headers.Authorization = "Bearer " + store.token;
  store.loading++;
  try {
    const res = await fetch(API + path, {
      method,
      headers,
      body: form ? body : body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!form && data.code === 401) {
      store.token = "";
      localStorage.removeItem("cbc_token");
      store.user = null;
      requestLogin();
      throw new Error("登录已过期");
    }
    if (data.code !== 0) {
      const error = new Error(data.msg || (form ? "上传失败" : "请求失败"));
      if (!form) error.payload = data;
      throw error;
    }
    return data.data;
  } finally {
    // 成功、失败和登录过期都必须结束本次加载计数。
    store.loading--;
  }
}

function api(path, options) {
  return apiRequest(path, options);
}

function apiForm(path, formData) {
  return apiRequest(path, { method: "POST", body: formData }, true);
}

function fmtPrice(value) {
  const price = Number(value);
  if (Number.isNaN(price)) return "0";
  return Number.isInteger(price) ? String(price) : price.toFixed(2);
}
function levelClass(level) {
  if (level === "优秀") return "lv-excellent";
  if (level === "良好") return "lv-good";
  if (level === "受限") return "lv-restricted";
  return "lv-fair";
}
function useBusy() {
  const busy = ref(false);
  async function run(action) {
    if (busy.value) return;
    busy.value = true;
    try {
      return await action();
    } finally {
      busy.value = false;
    }
  }
  return { busy, run };
}

const STATUS_TEXT = {
  pending: "待确认", confirmed: "已确认", pending_handoff: "待交接", completed: "已完成",
  canceled: "已取消", appealed: "已申诉", closed: "已关闭",
};
const LISTING_STATUS = {
  on_sale: "在架", reserved: "已预约", sold: "已售出", off_shelf: "已下架", expired: "已过期", banned: "违规下架",
};

function parseHash() {
  // 例如 #/book/12?from=market，解析为页面名及参数，不请求新的 HTML。
  const hash = location.hash.replace(/^#\/?/, "") || "home";
  const [pathPart, queryPart] = hash.split("?");
  const [name, ...rest] = pathPart.split("/");
  const params = { id: rest[0] };
  if (queryPart) {
    for (const [key, value] of new URLSearchParams(queryPart)) params[key] = value;
  }
  return { name: name || "home", params };
}
function go(path) {
  location.hash = "#/" + path;
}
function requestLogin(destination = location.hash.replace(/^#\/?/, "")) {
  if (destination && !destination.startsWith("login")) sessionStorage.setItem("bookloop_return", destination);
  go("login");
}
