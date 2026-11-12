/* ---------------- 组件：我的 ---------------- */
const MeView = {
  template: `
  <div class="container profile-page">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13"/><span>我的书架</span></div>
    <div class="card profile-card" v-if="me.id">
      <div class="row">
        <div class="profile-identity"><span class="avatar">{{ (me.nickname || me.name || '同学').slice(-2,-1) || '书' }}</span><div><span class="eyebrow">MY LITTLE BOOK CORNER</span><h1>{{ me.nickname || me.name }}的书架</h1><p>{{ me.college }} · 学号 {{ me.student_no }} <span class="tag" :class="levelClass(me.credit_level)">{{ me.credit_level }}</span></p></div></div>
        <span>
          <button class="btn small ghost" v-if="isStaff" @click="go(store.user?.role==='admin' ? 'admin' : 'points')">{{ store.user?.role==='admin' ? '管理后台' : '交接管理' }}</button>
          <button class="text-button" @click="logout"><ui-icon name="logout" :size="14"/>退出登录</button>
        </span>
      </div>
      <div class="grid grid-4 profile-stats">
        <div class="stat-tile" @click="jump('listings')"><div class="stat-num">{{ me.on_sale_count }}</div><div class="stat-label">在架</div></div>
        <div class="stat-tile" @click="go('orders')"><div class="stat-num">{{ me.deal_count }}</div><div class="stat-label">成交</div></div>
        <div class="stat-tile" :class="{alert: unread > 0}" @click="jump('msgs')"><div class="stat-num">{{ unread }}</div><div class="stat-label">未读消息</div></div>
        <div class="stat-tile" @click="jump('credit')"><div class="stat-num">{{ me.credit_score }}</div><div class="stat-label">我的信用分</div></div>
      </div>
      <div class="row" v-if="tab==='settings'" style="margin-top:12px;border-top:1px solid var(--border);padding-top:10px">
        <span class="muted" style="font-size:12px">
          <template v-if="wx.bound">已绑定微信：{{ wx.nickname }}</template>
          <template v-else>未绑定微信（绑定后可扫码免密登录）</template>
        </span>
        <span v-if="!wx.bound">
          <input v-model="wxCode" placeholder="授权码（演示填任意串）" style="height:30px;width:150px;border:1px solid var(--border);border-radius:6px;padding:0 8px;margin-right:6px" />
          <button class="btn small ghost" :disabled="busy" @click="bindWechat">绑定</button>
        </span>
        <span v-else>
          <button class="btn small ghost" :disabled="busy" @click="unbindWechat">解绑</button>
        </span>
      </div>
    </div>

    <div class="profile-layout"><aside class="profile-sidebar"><nav class="nav-tabs profile-menu" aria-label="个人中心"><button :class="{active: tab==='listings'}" @click="tab='listings'"><ui-icon name="book"/>我的发布</button><button @click="go('orders')"><ui-icon name="order"/>我买到的 / 交易订单</button><button :class="{active: tab==='wanteds'}" @click="tab='wanteds'"><ui-icon name="search"/>我的求购</button><button :class="{active: tab==='favs'}" @click="tab='favs'"><ui-icon name="heart"/>我的收藏</button><button :class="{active: tab==='credit'}" @click="tab='credit'"><ui-icon name="star"/>信用记录</button><button :class="{active: tab==='msgs'}" @click="tab='msgs'"><ui-icon name="message"/>消息通知 <span v-if="unread" class="tag">{{ unread }}</span></button><button :class="{active: tab==='points'}" @click="tab='points';loadPoints()"><ui-icon name="pin"/>我的交接点</button><button :class="{active: tab==='settings'}" @click="tab='settings'"><ui-icon name="user"/>账号设置</button></nav><div class="profile-sidebar-note"><ui-icon name="leaf" :size="27"/><p>一方小书架，<br/>装下大世界。</p></div></aside><section class="profile-content"><div class="profile-content-heading"><h2>{{ tabTitles[tab] }}</h2><a class="text-link" href="#/publish"><ui-icon name="plus" :size="15"/>再分享一本好书</a></div>

    <div class="card" v-if="tab==='listings'">
      <div v-if="!dash.listings.length" class="empty">还没有发布记录</div>
      <div class="order-item" v-for="l in dash.listings" :key="l.id">
        <div class="profile-book-row"><book-cover :title="l.title || l.book_title || '校园教材'" :src="l.images?.[0] || l.cover || ''" :fallback-src="l.cover || ''"/><div>
        <div class="row"><b>{{ l.title }}</b><span class="tag">{{ LISTING_STATUS[l.status] || l.status }}</span></div>
        <div class="muted" style="font-size:12px">{{ l.condition_level }} · ¥{{ fmtPrice(l.price) }} · 浏览 {{ l.view_count }}</div>
        <div class="row" style="margin-top:6px">
          <span class="muted" style="font-size:12px">{{ l.created_at ? l.created_at.slice(0,10) : '' }}</span>
          <span>
            <button class="btn small ghost" :disabled="busy" v-if="l.status==='on_sale'" @click="act(l,'off_shelf')">下架</button>
            <button class="btn small ghost" :disabled="busy" v-if="l.status==='off_shelf'" @click="act(l,'on_shelf')">上架</button>
            <button class="btn small ghost" :disabled="busy" @click="act(l,'refresh')">刷新</button>
            <button class="btn small ghost" :disabled="busy" style="color:var(--danger)" v-if="!['sold','reserved'].includes(l.status)" @click="delListing(l)">删除</button>
          </span>
        </div>
        </div></div>
      </div>
    </div>

    <div class="card" v-if="tab==='wanteds'">
      <div v-if="!dash.wanteds.length" class="empty">暂无求购</div>
      <div class="order-item" v-for="w in dash.wanteds" :key="w.id">
        <div class="row"><b>{{ w.book_title }}</b><span class="tag">{{ w.status==='open' ? '正在寻找' : '已结束' }}</span></div>
        <div class="row" style="margin-top:6px">
          <span class="muted" style="font-size:12px">成色下限 {{ w.min_condition }} · 心理价位 ¥{{ w.max_price }}</span>
          <button class="btn small ghost" :disabled="busy" style="color:var(--danger)" @click="delWanted(w)">删除</button>
        </div>
      </div>
    </div>

    <div class="card" v-if="tab==='favs'">
      <div v-if="!favs.length" class="empty">暂无收藏</div>
      <div class="order-item" v-for="f in favs" :key="f.book_id">
        <div class="row"><span @click="go('book/'+f.book_id)" style="cursor:pointer">{{ f.title }}</span><span class="tag">{{ f.on_sale }} 本在架</span></div>
        <div class="row" style="margin-top:6px">
          <span></span>
          <button class="btn small ghost" :disabled="busy" style="color:var(--danger)" @click="unfav(f)">取消收藏</button>
        </div>
      </div>
    </div>

    <div class="card" v-if="tab==='settings'"><h3>账号与隐私</h3><p class="muted">你的学号和手机号经加密保存，交易确认前对方无法查看完整联系方式。微信绑定可在上方个人资料区管理。</p><a class="text-link" href="./user-agreement.html" target="_blank" rel="noopener">查看用户协议 <ui-icon name="arrow" :size="16"/></a></div>

    <div class="card" v-if="tab==='credit'">
      <h3>信用分 {{ credit.score }}（<span class="tag" :class="levelClass(credit.level)">{{ credit.level }}</span>）</h3>
      <div v-if="!credit.logs.length" class="empty">暂无信用记录</div>
      <div class="order-item" v-for="(c, i) in credit.logs" :key="i">
        <div class="row"><span>{{ c.reason }}</span><span :style="c.delta>=0 ? 'color:var(--brand)' : 'color:var(--danger)'">{{ c.delta>=0?'+':'' }}{{ c.delta }}</span></div>
        <div class="muted" style="font-size:12px">变动后 {{ c.score_after }} 分 · {{ c.created_at ? c.created_at.slice(0,10) : '' }}</div>
      </div>
    </div>

    <div class="card" v-if="tab==='msgs'">
      <div class="row" style="margin-bottom:8px">
        <b>站内消息</b>
        <span>
          <button class="btn ghost small" v-if="msgs.some(m=>!m.is_read)" @click="readAll">全部标为已读</button>
          <button class="btn ghost small" v-if="msgs.length" style="color:var(--danger)" @click="clearMsgs">清空全部</button>
        </span>
      </div>
      <div v-if="!msgs.length" class="empty">暂无消息</div>
      <div class="order-item" :class="{unread: !m.is_read}" v-for="m in msgs" :key="m.id" @click="readMsg(m)">
        <div class="row"><b>{{ m.title }}</b><span class="tag gray">{{ m.is_read ? '已读' : '未读' }}</span></div>
        <div class="muted" style="font-size:12px">{{ m.content }}</div>
        <div class="row" style="margin-top:6px">
          <span class="muted" style="font-size:12px">{{ m.created_at ? m.created_at.replace('T',' ').slice(0,16) : '' }}</span>
          <button class="btn small ghost" :disabled="busy" style="color:var(--danger)" @click.stop="delMsg(m)">删除</button>
        </div>
      </div>
    </div>

    <div class="card" v-if="tab==='points'">
      <div class="row" style="margin-bottom:10px">
        <b>我自定义的交接点</b>
        <span class="muted" style="font-size:12px">仅自己可见 · 最多 5 个</span>
      </div>
      <div v-if="!myPoints.length" class="empty">还没有自定义交接点</div>
      <div class="order-item" v-for="p in myPoints" :key="p.id">
        <div class="row">
          <b>{{ p.name }}</b>
          <button class="btn small ghost" :disabled="busy" style="color:var(--danger)" @click="delPoint(p)">删除</button>
        </div>
        <div class="muted" style="font-size:12px">{{ p.location || '未填写位置' }} · {{ p.open_time }}-{{ p.close_time }}</div>
      </div>
      <div style="border-top:1px solid var(--border);margin-top:10px;padding-top:10px">
        <div class="grid grid-2 keep">
          <div class="field"><label>名称（必填）</label><input v-model="np.name" maxlength="40" placeholder="如：3 号宿舍楼门口" /></div>
          <div class="field"><label>位置描述</label><input v-model="np.location" maxlength="120" placeholder="如：东区 3 号楼门厅" /></div>
        </div>
        <div class="grid grid-2 keep">
          <div class="field"><label>开放时间</label><input type="time" v-model="np.open_time" /></div>
          <div class="field"><label>关闭时间</label><input type="time" v-model="np.close_time" /></div>
        </div>
        <button class="btn small" :disabled="busy" @click="addPoint">添加交接点</button>
      </div>
    </div>
    </section></div>
  </div>`,
  setup() {
    const me = ref({});
    const dash = ref({ listings: [], wanteds: [], orders: [] });
    const favs = ref([]);
    const msgs = ref([]);
    const unread = ref(0);
    const credit = reactive({ score: 0, level: "", can_publish: true, logs: [] });
    const wx = reactive({ bound: false, nickname: "" });
    const wxCode = ref("");
    const tabTitles = {listings:"我发布的好书",wanteds:"我的求购",favs:"我的收藏",credit:"信用记录",msgs:"消息通知",points:"我的交接点",settings:"账号设置"};
    const tab = ref(Object.hasOwn(tabTitles, store.route.params.tab) ? store.route.params.tab : "listings");
    const loading = ref(false);
    const myPoints = ref([]);
    const np = reactive({ name: "", location: "", open_time: "08:00", close_time: "20:00" });
    const { busy, run } = useBusy();

    async function loadPoints() {
      try { myPoints.value = await api("/handoff/points/mine"); } catch (e) { setError(e.message); }
    }
    function addPoint() {
      if (!np.name.trim()) return setError("请填写交接点名称");
      return run(async () => {
        await api("/handoff/points/mine", { method: "POST", body: { ...np, name: np.name.trim() } });
        np.name = ""; np.location = "";
        setNotice("交接点已添加");
        await loadPoints();
      }).catch((e) => setError(e.message));
    }
    function delPoint(p) {
      return run(async () => {
        await api("/handoff/points/mine/" + p.id, { method: "DELETE" });
        setNotice("已删除");
        await loadPoints();
      }).catch((e) => setError(e.message));
    }

    function jump(t) {
      tab.value = t;
      nextTick(() => {
        const el = document.querySelector(".nav-tabs");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    async function load() {
      loading.value = true;
      try {
        me.value = await api("/auth/me");
        dash.value = await api("/auth/dashboard");
        favs.value = await api("/search/favorites/mine");
        const m = await api("/auth/messages");
        msgs.value = m.items; unread.value = m.unread;
        const c = await api("/auth/credit");
        Object.assign(credit, c);
        const w = await api("/auth/wechat/status");
        wx.bound = w.bound; wx.nickname = w.nickname;
      } catch (e) { setError(e.message); }
      finally { loading.value = false; }
    }
    async function bindWechat() {
      try {
        await api("/auth/wechat/bind?code=" + encodeURIComponent(wxCode.value || "demo"), { method: "POST" });
        setNotice("微信绑定成功"); wxCode.value = ""; load();
      } catch (e) { setError(e.message); }
    }
    async function unbindWechat() {
      try {
        await api("/auth/wechat/unbind", { method: "POST" });
        setNotice("已解绑微信"); load();
      } catch (e) { setError(e.message); }
    }
    function act(l, action) {
      return run(async () => {
        await api("/listings/" + l.id + "/" + (action === "refresh" ? "refresh" : (action === "on_shelf" ? "on-shelf" : "off-shelf")), { method: "POST" });
        setNotice("操作成功"); load();
      }).catch((e) => setError(e.message));
    }
    async function readMsg(m) {
      if (m.is_read) return;
      try {
        await api("/auth/messages/" + m.id + "/read", { method: "POST" });
        m.is_read = true; unread.value = Math.max(0, unread.value - 1);
      } catch (e) {}
    }
    async function readAll() {
      await Promise.all(msgs.value.filter((m) => !m.is_read).map(readMsg));
      setNotice("已全部标记为已读");
    }
    function delListing(l) {
      if (!confirm("确定删除该发布？此操作不可恢复。")) return;
      return run(async () => {
        await api("/listings/" + l.id, { method: "DELETE" });
        setNotice("已删除"); load();
      }).catch((e) => setError(e.message));
    }
    function delWanted(w) {
      if (!confirm("确定删除该求购？")) return;
      return run(async () => {
        await api("/listings/wanted/" + w.id, { method: "DELETE" });
        setNotice("已删除"); load();
      }).catch((e) => setError(e.message));
    }
    function unfav(f) {
      return run(async () => {
        await api("/search/favorites/" + f.book_id, { method: "DELETE" });
        setNotice("已取消收藏"); load();
      }).catch((e) => setError(e.message));
    }
    function delMsg(m) {
      return run(async () => {
        await api("/auth/messages/" + m.id, { method: "DELETE" });
        setNotice("已删除"); load();
      }).catch((e) => setError(e.message));
    }
    function clearMsgs() {
      if (!confirm("确定清空全部消息？")) return;
      return run(async () => {
        await api("/auth/messages", { method: "DELETE" });
        setNotice("已清空"); load();
      }).catch((e) => setError(e.message));
    }
    function logout() {
      store.token = ""; store.user = null; localStorage.removeItem("cbc_token"); go("login");
    }
    const isStaff = computed(() => store.user && ["admin", "point_admin"].includes(store.user.role));
    onMounted(() => { load(); if (tab.value==='points') loadPoints(); });
    watch(() => store.route.params.tab, (value) => { if (Object.hasOwn(tabTitles, value)) tab.value = value; });
    return { store, tabTitles, me, dash, favs, msgs, unread, credit, wx, wxCode, tab, loading, busy, myPoints, np,
             loadPoints, addPoint, delPoint, jump,
             act, readMsg, readAll, delListing, delWanted, unfav, delMsg, clearMsgs,
             bindWechat, unbindWechat, logout, go, isStaff, LISTING_STATUS };
  },
};
