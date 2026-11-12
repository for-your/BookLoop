/* ---------------- 组件：订单 ---------------- */
const OrdersView = {
  template: `
  <div class="container orders-page">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13"/><a href="#/me">我的书架</a><ui-icon name="chevron" :size="13"/><span>交易订单</span></div>
    <header class="page-heading"><div><span class="eyebrow">EVERY HANDOFF TELLS A STORY</span><h1>每一份预约，都值得如期而至。</h1><p>确认预约 → 约定时间 → 当面验书 → 交接核销 → 留下评价</p></div><a class="text-link" href="#/points">查看校园交接点<ui-icon name="arrow" :size="17"/></a></header>
    <div class="nav-tabs">
      <button :class="{active: tab==='all'}" @click="tab='all';load()">全部</button>
      <button :class="{active: tab==='pending'}" @click="tab='pending';load()">待确认</button>
      <button :class="{active: tab==='confirmed'}" @click="tab='confirmed';load()">待交接</button>
      <button :class="{active: tab==='completed'}" @click="tab='completed';load()">已完成</button>
    </div>

    <div class="card">
      <div v-if="loading" class="spinner">正在加载…</div>
      <div v-else-if="!items.length" class="empty">暂无订单</div>
      <div class="order-item" v-for="o in items" :key="o.id">
        <div class="row">
          <div>
            <b>{{ o.book_title }}</b> <span class="tag">{{ STATUS_TEXT[o.status] }}</span>
            <span class="tag gray">{{ o.role==='buyer' ? '我买的' : '我卖的' }}</span>
          </div>
          <div class="price">¥{{ fmtPrice(o.price) }}</div>
        </div>
        <div class="muted" style="font-size:12px">
          订单号 {{ o.order_no }} · 对方 {{ o.role==='buyer' ? o.seller_name : o.buyer_name }} · {{ o.point_name }}
        </div>
        <div class="muted" style="font-size:12px">约定时间：{{ o.appoint_at ? o.appoint_at.replace('T',' ').slice(0,16) : '待定' }}</div>
        <div v-if="o.verify_code" class="code-box" style="margin-top:8px">{{ o.verify_code }}</div>
        <div class="row" style="margin-top:8px;flex-wrap:wrap;gap:6px">
          <button class="btn small" :disabled="busy" v-if="o.status==='pending' && o.role==='seller'" @click="confirm(o)">确认预约</button>
          <button class="btn small ghost" :disabled="busy" v-if="['confirmed','pending_handoff'].includes(o.status)" @click="showVerify(o)">核销</button>
          <button class="btn small ghost" :disabled="busy" v-if="['pending','confirmed','pending_handoff'].includes(o.status)" @click="cancel(o)">取消（违约扣分）</button>
          <button class="btn small ghost" :disabled="busy" v-if="o.status==='completed'" @click="showReview(o)">评价</button>
          <button class="btn small ghost" :disabled="busy" v-if="o.status==='completed'" @click="showAppeal(o)">申诉</button>
        </div>
      </div>
    </div>

    <div class="modal-mask" v-if="verify.order" @click.self="verify.order=null">
      <div class="modal">
        <h3>交接核销</h3>
        <div class="field"><label>核销码（6 位）</label><input v-model="verify.code" /></div>
        <button class="btn" style="width:100%" :disabled="busy" @click="doVerify">确认核销</button>
      </div>
    </div>

    <div class="modal-mask" v-if="review.order" @click.self="review.order=null">
      <div class="modal">
        <h3>评价对方</h3>
        <div class="field"><label>描述相符</label>
          <div class="stars"><span v-for="n in 5" :key="n" class="star" :class="{on: n<=review.desc}" @click="review.desc=n">★</span></div>
        </div>
        <div class="field"><label>成色真实</label>
          <div class="stars"><span v-for="n in 5" :key="n" class="star" :class="{on: n<=review.cond}" @click="review.cond=n">★</span></div>
        </div>
        <div class="field"><label>履约及时</label>
          <div class="stars"><span v-for="n in 5" :key="n" class="star" :class="{on: n<=review.punct}" @click="review.punct=n">★</span></div>
        </div>
        <div class="field"><label>文字评价</label><textarea v-model="review.comment"></textarea></div>
        <button class="btn" style="width:100%" :disabled="busy" @click="doReview">提交评价</button>
      </div>
    </div>

    <div class="modal-mask" v-if="appeal.order" @click.self="appeal.order=null">
      <div class="modal">
        <h3>交易申诉</h3>
        <div class="field"><label>申诉类型</label>
          <select v-model="appeal.type">
            <option>货不对板</option><option>缺页</option><option>未到场</option><option>其他</option>
          </select>
        </div>
        <div class="field"><label>说明</label><textarea v-model="appeal.detail"></textarea></div>
        <button class="btn" style="width:100%" :disabled="busy" @click="doAppeal">提交申诉</button>
      </div>
    </div>

    <div class="modal-mask" v-if="cancelTarget" @click.self="cancelTarget=null">
      <div class="modal">
        <h3>确认取消订单</h3>
        <p class="muted" style="font-size:13px">取消将扣除信用分（临近交接 2 小时内扣 10 分，否则扣 5 分），确定继续？</p>
        <div class="row" style="gap:8px;margin-top:12px">
          <button class="btn ghost" style="flex:1" @click="cancelTarget=null">再想想</button>
          <button class="btn danger" style="flex:1" :disabled="busy" @click="doCancel">确定取消</button>
        </div>
      </div>
    </div>
  </div>`,
  setup() {
    const tab = ref("all");
    const items = ref([]);
    const loading = ref(false);
    const verify = reactive({ order: null, code: "" });
    const review = reactive({ order: null, desc: 5, cond: 5, punct: 5, comment: "" });
    const appeal = reactive({ order: null, type: "货不对板", detail: "" });
    const cancelTarget = ref(null);
    const { busy, run } = useBusy();

    async function load() {
      loading.value = true;
      try { items.value = await api("/orders" + (tab.value === "all" ? "" : "?status=" + tab.value)); }
      catch (e) { setError(e.message); }
      finally { loading.value = false; }
    }
    function confirm(o) {
      return run(async () => {
        await api("/orders/" + o.id + "/confirm", { method: "POST", body: {} });
        setNotice("已确认"); load();
      }).catch((e) => setError(e.message));
    }
    function cancel(o) { cancelTarget.value = o; }
    function doCancel() {
      const o = cancelTarget.value;
      if (!o) return;
      return run(async () => {
        await api("/orders/" + o.id + "/cancel", { method: "POST", body: { reason: "用户取消" } });
        setNotice("订单已取消"); cancelTarget.value = null; load();
      }).catch((e) => setError(e.message));
    }
    function showVerify(o) { verify.order = o; verify.code = ""; }
    function doVerify() {
      return run(async () => {
        await api("/orders/" + verify.order.id + "/verify", { method: "POST", body: { code: verify.code } });
        setNotice("核销成功，交易完成"); verify.order = null; load();
      }).catch((e) => setError(e.message));
    }
    function showReview(o) { review.order = o; review.comment = ""; review.desc = review.cond = review.punct = 5; }
    function doReview() {
      return run(async () => {
        await api("/reviews", { method: "POST", body: { order_id: review.order.id, rating_desc: review.desc, rating_condition: review.cond, rating_punctual: review.punct, comment: review.comment } });
        setNotice("评价已提交"); review.order = null; load();
      }).catch((e) => setError(e.message));
    }
    function showAppeal(o) { appeal.order = o; appeal.detail = ""; }
    function doAppeal() {
      return run(async () => {
        await api("/orders/" + appeal.order.id + "/appeal", { method: "POST", body: { reason_type: appeal.type, detail: appeal.detail } });
        setNotice("申诉已提交"); appeal.order = null; load();
      }).catch((e) => setError(e.message));
    }
    onMounted(load);
    return { tab, items, loading, verify, review, appeal, cancelTarget, busy, load, confirm, cancel, doCancel, showVerify, doVerify, showReview, doReview, showAppeal, doAppeal, STATUS_TEXT };
  },
};
