/* ---------------- 组件：交接点 ---------------- */
const PointsView = {
  template: `
  <div class="container points-page">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13"/><span>校园交接点</span></div>
    <header class="page-heading"><div><span class="eyebrow">MEET ON CAMPUS, PASS ON KNOWLEDGE</span><h1>约在校园，让知识接力。</h1><p>选择合适的交接点，核对开放时间，带上你的好书赴约。</p></div><ui-icon name="pin" :size="36"/></header>
    <div class="card" style="padding:10px 14px">
      <div class="row">
        <span class="muted" style="font-size:12px">找不到合适的交接点？可以自定义一个仅自己可见的（如宿舍楼下）。</span>
        <button class="btn small ghost" @click="go('me')">去设置</button>
      </div>
    </div>
    <div class="card" v-for="p in points" :key="p.id">
      <div class="row">
        <div>
          <b>{{ p.name }}</b> <span class="tag" v-if="p.mine">自定义</span>
          <div class="muted" style="font-size:12px">{{ p.location }} · {{ p.district }} · {{ p.open_time }}-{{ p.close_time }}</div>
          <div class="muted" style="font-size:12px">今日剩余容量 {{ p.today_remain }} / {{ p.today_total }}<span v-if="p.distance_km"> · 距你约 {{ p.distance_km }} km</span></div>
        </div>
        <button class="btn small ghost" @click="open(p)">查看时段</button>
      </div>
      <div v-if="cur===p.id" style="margin-top:10px">
        <div class="muted" style="font-size:12px;margin-bottom:6px">30 分钟一段，单时段容量 {{ slotCap }} 单</div>
        <div class="grid grid-4">
          <div v-for="s in slots" :key="s.start_time" class="card" style="margin:0;padding:8px;text-align:center;font-size:12px">
            <div>{{ s.start_time }}-{{ s.end_time }}</div>
            <div class="muted">余 {{ s.remain }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card" v-if="isStaff">
      <h3>交接点核销（管理员）</h3>
      <div class="row" style="gap:8px">
        <input style="height:38px;flex:1;border-radius:8px;border:1px solid var(--border);padding:0 10px" v-model="code" placeholder="输入 6 位核销码或扫码" />
        <button class="btn" @click="doVerify">核销</button>
      </div>
      <div class="hint muted" style="margin-top:8px">异常登记（未带证件 / 教材不符）：</div>
      <div class="row" style="gap:8px;margin-top:4px">
        <input style="height:34px;width:110px;border-radius:6px;border:1px solid var(--border);padding:0 8px" v-model="orderId" placeholder="订单号" />
        <input style="height:34px;flex:1;border-radius:6px;border:1px solid var(--border);padding:0 8px" v-model="reason" placeholder="如：未带证件" />
        <button class="btn small ghost" @click="abnormal">登记</button>
      </div>
    </div>
  </div>`,
  setup() {
    const points = ref([]);
    const slots = ref([]);
    const cur = ref(null);
    const code = ref("");
    const reason = ref("");
    const orderId = ref("");
    const slotCap = ref(20);
    const isStaff = computed(() => store.user && ["point_admin", "admin"].includes(store.user.role));

    async function open(p) {
      cur.value = cur.value === p.id ? null : p.id;
      if (!cur.value) return;
      try { slots.value = (await api("/handoff/points/" + p.id + "/slots")).items; } catch (e) { setError(e.message); }
    }
    async function doVerify() {
      try { const d = await api("/handoff/verify?code=" + code.value, { method: "POST" }); setNotice("核销成功：" + d.order_no); code.value = ""; }
      catch (e) { setError(e.message); }
    }
    async function abnormal() {
      if (!orderId.value || !reason.value) return setError("请填写订单号与异常原因");
      try {
        await api("/handoff/abnormal?order_id=" + Number(orderId.value) + "&reason=" + encodeURIComponent(reason.value), { method: "POST" });
        setNotice("异常已登记"); reason.value = "";
      } catch (e) { setError(e.message); }
    }
    onMounted(async () => {
      try { points.value = await api("/handoff/points"); } catch (e) { setError(e.message); }
    });
    return { points, slots, cur, code, reason, orderId, slotCap, isStaff, open, doVerify, abnormal, go };
  },
};
