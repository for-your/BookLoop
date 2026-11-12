/* ---------------- 根组件 ---------------- */
const App = {
  template: `
  <div class="app">
    <a class="skip-link" href="#main-content" @click.prevent="focusContent">跳到主要内容</a>
    <div class="loading-bar" v-if="store.loading"></div>
    <header class="site-header">
    <div class="topbar site-width">
      <a class="brand" href="#/home" aria-label="书循首页"><img src="./assets/bookloop.svg" width="43" height="43" alt=""/><span><strong>书循<span class="brand-period">.</span></strong><small>BOOKLOOP · 校园流动书房</small></span></a>
      <nav class="desktop-nav" aria-label="主导航"><a v-for="item in navigation" :key="item.path" :href="'#/'+item.path" :class="{active: store.route.name===item.path || (item.path==='market' && ['book','reading'].includes(store.route.name))}" :aria-current="store.route.name===item.path ? 'page' : null">{{ item.label }}</a></nav>
      <div class="search-wrap" @focusout="sugBlur">
        <ui-icon name="search" :size="17"/>
        <input class="search" ref="searchInput" v-model="store.keyword" placeholder="搜索书名、作者、课程…"
               aria-label="搜索书名、书籍编号或课程" @input="onSugInput" @focus="onSugInput" @keyup.enter="doSearch" @keydown.esc="closeSug" />
        <kbd>/</kbd>
        <div class="sug-box" v-if="sugOpen && (sugBooks.length || sugCourses.length)">
          <template v-if="sugBooks.length">
            <div class="sug-group">教材</div>
            <button class="sug-item" v-for="b in sugBooks" :key="'b'+b.id" @click="pickBook(b)">
              <span class="sug-title">{{ b.title }}</span>
              <span class="sug-sub">{{ b.isbn }}</span>
            </button>
          </template>
          <template v-if="sugCourses.length">
            <div class="sug-group">课程</div>
            <button class="sug-item" v-for="c in sugCourses" :key="'c'+c.id" @click="pickCourse(c)">
              <span class="sug-title">{{ c.name }}</span>
              <span class="sug-sub">{{ c.code }}</span>
            </button>
          </template>
        </div>
      </div>
      <div class="header-actions"><button class="icon-button notification-button" aria-label="消息通知" @click="go('me?tab=msgs')"><ui-icon name="bell" :size="20"/></button><button v-if="store.token" class="avatar" @click="go('me')" :aria-label="'个人中心：'+(store.user?.nickname || '我的')">{{ (store.user?.nickname || '同学').slice(-2,-1) || '书' }}</button><button class="login-link" v-else @click="go('login')">登录<span> / 注册</span></button><button class="btn publish-entry" @click="go('publish')"><ui-icon name="plus" :size="16"/>发布书籍</button></div>
    </div>
    </header>

    <div class="toast-stack" aria-live="polite">
      <div class="banner" role="alert" v-if="store.error"><ui-icon name="close" :size="18"/>{{ store.error }}<button class="icon-button" aria-label="关闭错误提示" @click="store.error=''">×</button></div>
      <div class="banner ok" v-if="store.notice"><ui-icon name="check" :size="18"/>{{ store.notice }}</div>
    </div>

    <main id="main-content" tabindex="-1" :data-page="store.route.name"><component :is="view" :key="store.route.name + (store.route.params.id || '')" /></main>

    <footer class="site-footer"><div class="site-width footer-invitation"><div><span class="eyebrow">THE NEXT CHAPTER IS YOURS</span><h2>好书的下一站，<span>也许就是你。</span></h2></div><a class="footer-round-link" href="#/reading" aria-label="探索校园书架"><ui-icon name="diagonal" :size="29"/></a></div><div class="site-width footer-main"><div class="footer-brand"><a class="brand" href="#/home"><img src="./assets/bookloop.svg" width="36" height="36" alt=""/><strong>书循</strong></a><p>书页有终章，知识无尽时。<br/>让一本旧书，开启一段新的校园故事。</p></div><div><h4>发现好书</h4><a href="#/reading">校园选书</a><a href="#/market">书籍集市</a><a href="#/market?mode=course">课程找书</a></div><div><h4>书页之外</h4><a href="#/news">校园阅读指南</a><a href="#/activities">教材循环计划</a><a href="#/about">关于书循</a></div><div><h4>安心流转</h4><a href="#/points">校园交接点</a><button @click="showHelp=true">交易与信用规则</button><a href="./user-agreement.html" target="_blank" rel="noopener">用户协议</a></div><div class="footer-note"><ui-icon name="leaf" :size="30"/><p>以书为媒，以循为约。</p><span>成都信息工程大学 · 校园二手书流转平台</span></div></div><div class="footer-bottom site-width"><span>© {{ new Date().getFullYear() }} 书循 BookLoop</span><span>MADE FOR OUR CAMPUS <ui-icon name="leaf" :size="13"/></span></div></footer>

    <nav class="bottom-nav" aria-label="移动端导航"><a v-for="item in mobileNavigation" :key="item.path" :href="'#/'+item.path" :class="{active: store.route.name===item.path}"><ui-icon :name="item.icon" :size="21"/><span>{{ item.label }}</span></a></nav>

    <assistant-panel/>

    <div class="modal-mask" v-if="showHelp" @click.self="showHelp=false">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="help-title">
        <div class="row"><h3 id="help-title">安心交易 · 使用指南</h3><button class="icon-button" aria-label="关闭使用指南" @click="showHelp=false"><ui-icon name="close"/></button></div>
        <div class="help-body">
          <p><b>交易流程</b>：发布 → 检索匹配 → 预约 → 双方确认 → 交接点核销 → 互评</p>
          <p><b>交易规则</b>：售价不超过原价 70%；信用分低于 60 禁止发布；单方取消扣 5 分（临近 2 小时扣 10 分）</p>
          <p><b>核销</b>：交接点管理员扫码或输入 6 位核销码完成交付</p>
          <p><b>申诉</b>：交付后 7 日内可申诉，管理员 3 个工作日裁定</p>
          <p><b>快捷键</b>：<code>/</code> 聚焦搜索框，<code>Esc</code> 关闭提示</p>
          <p><b>举报</b>：如遇虚假描述、盗版教材，可在「我的」页面联系管理员或提交举报</p>
        </div>
        <button class="btn" style="width:100%" @click="showHelp=false">知道了</button>
      </div>
    </div>
  </div>`,
  setup() {
    const searchInput = ref(null);
    const navigation = [{path:"home",label:"首页"},{path:"market",label:"书籍集市"},{path:"news",label:"校园资讯"},{path:"activities",label:"校园活动"},{path:"about",label:"关于书循"}];
    const mobileNavigation = [{path:"home",label:"首页",icon:"home"},{path:"market",label:"集市",icon:"book"},{path:"publish",label:"发布",icon:"plus"},{path:"orders",label:"订单",icon:"order"},{path:"me",label:"我的",icon:"user"}];
    const views = { home: DiscoverView, reading: ReadingView, market: MarketView, news: CampusView, activities: CampusView, about: CampusView, book: BookView, publish: PublishView, orders: OrdersView, points: PointsView, me: MeView, admin: AdminView, login: LoginView };
    const view = computed(() => views[store.route.name] || DiscoverView);

    async function ensureUser() {
      if (store.token && !store.user) {
        try { store.user = await api("/auth/me"); } catch (e) { store.token = ""; }
      }
    }
    function doSearch() { closeSug(); go("market" + (store.keyword.trim() ? "?kw=" + encodeURIComponent(store.keyword.trim()) : "")); }
    function focusContent() { document.getElementById("main-content")?.focus(); }
    const showHelp = ref(false);

    /* ---- 顶栏搜索联想：300ms 防抖，教材 + 课程两组 ---- */
    const sugOpen = ref(false);
    const sugBooks = ref([]);
    const sugCourses = ref([]);
    let sugTimer = null;
    let sugSeq = 0;

    async function fetchSugs() {
      const kw = store.keyword.trim();
      const seq = ++sugSeq;
      if (!kw) { sugOpen.value = false; sugBooks.value = []; sugCourses.value = []; return; }
      try {
        const [b, c] = await Promise.all([
          api("/catalog/books?keyword=" + encodeURIComponent(kw) + "&size=4"),
          api("/catalog/courses?keyword=" + encodeURIComponent(kw)),
        ]);
        if (seq !== sugSeq) return; // 已有更新的请求，丢弃旧结果
        sugBooks.value = (b.items || []).slice(0, 4);
        sugCourses.value = (Array.isArray(c) ? c : c.items || []).slice(0, 3);
        sugOpen.value = true;
      } catch (e) { /* 联想失败不打扰主流程 */ }
    }
    function onSugInput() {
      clearTimeout(sugTimer);
      sugTimer = setTimeout(fetchSugs, 300);
    }
    function pickBook(b) {
      sugOpen.value = false;
      store.keyword = b.title;
      go("book/" + b.id);
    }
    function pickCourse(c) {
      sugOpen.value = false;
      store.keyword = c.name; // 后端检索本身支持课程名/课程代码匹配
      go("market?course=" + c.id);
    }
    function closeSug() { sugOpen.value = false; }
    function sugBlur(event) { if (!event.currentTarget.contains(event.relatedTarget)) setTimeout(() => (sugOpen.value = false), 150); }

    async function handleWechatCallback() {
      const code = new URLSearchParams(location.search).get("code");
      if (!code) return;
      try {
        const data = await api("/auth/wechat/login?code=" + encodeURIComponent(code), { method: "POST" });
        if (data.need_bind) {
          localStorage.setItem("cbc_wx_pending", JSON.stringify({ token: data.wechat_token, nickname: data.nickname }));
          setNotice("微信尚未绑定账号，请绑定学号创建账号");
          go("login");
        } else {
          store.token = data.access_token;
          localStorage.setItem("cbc_token", data.access_token);
          store.user = data.user;
          setNotice("微信登录成功，欢迎回来，" + data.user.nickname);
          go("home");
        }
      } catch (e) {
        setError(e.message);
        go("login");
      } finally {
        history.replaceState(null, "", location.pathname);
      }
    }

    onMounted(async () => {
      window.addEventListener("hashchange", () => {
        const route = parseHash();
        if (!store.token && LOGIN_REQUIRED_ROUTES.includes(route.name)) {
          sessionStorage.setItem("bookloop_return", location.hash.slice(2));
          go("login");
          return;
        }
        store.route = route;
        window.scrollTo({ top: 0, behavior: "instant" });
      });
      window.addEventListener("keydown", (e) => {
        if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && !document.activeElement.isContentEditable) {
          e.preventDefault();
          if (searchInput.value) searchInput.value.focus();
        }
        if (e.key === "Escape") { store.error = ""; showHelp.value = false; }
      });
      await ensureUser();
      await handleWechatCallback();
    });

    watch(() => store.route.name, ensureUser);
    return { store, view, searchInput, go, doSearch, showHelp, navigation, mobileNavigation, focusContent,
             sugOpen, sugBooks, sugCourses, onSugInput, pickBook, pickCourse, closeSug, sugBlur };
  },
};

store.route = parseHash();
if (!store.token && LOGIN_REQUIRED_ROUTES.includes(store.route.name)) {
  sessionStorage.setItem("bookloop_return", location.hash.slice(2));
  go("login");
  store.route = { name: "login", params: {} };
}
