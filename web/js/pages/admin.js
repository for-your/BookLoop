/* ---------------- 组件：后台管理 ---------------- */
const LOG_ACTION_TEXT = {
  login: "登录", register: "注册", listing_create: "发布挂牌", listing_update: "编辑挂牌",
  listing_off: "下架", listing_delete: "删除挂牌", listing_ban: "违规下架",
  order_create: "预约下单", order_confirm: "确认预约", order_cancel: "取消订单",
  order_verify: "交接核销", report_handle: "举报处理", user_status: "账号状态",
  credit_adjust: "信用调整", donation_approve: "捐赠审核", param_update: "参数修改",
  appeal_judge: "申诉裁定", book_import: "教材导入", book_audit: "教材审核",
  point_create: "新增交接点", point_update: "交接点维护", point_delete: "删除交接点",
  point_create_self: "自定义交接点", point_delete_self: "删除自定义交接点",
  point_admin_cert: "交接点管理员认证",
};
const USER_STATUS_TEXT = { active: "正常", disabled: "已禁用" };
const ROLE_TEXT = { student: "学生", point_admin: "交接点管理员", admin: "平台管理员" };
const DONATION_STATUS_TEXT = { pending: "待审核", approved: "已通过", recycled: "已回收", donated: "已赠予" };
const TARGET_TEXT = { listing: "挂牌", user: "用户" };
const PARAM_NAME_TEXT = {
  price_ratio_max: "挂牌价上限比例", price_ratio_min_suggest: "建议售价下限比例",
  max_on_sale_per_user: "单用户在架上限", max_same_isbn_per_user: "同一书籍在架上限",
  listing_valid_days: "挂牌有效期（天）", reserve_lock_hours: "预约锁定时长（小时）",
  confirm_timeout_hours: "卖家确认超时（小时）", max_reschedule: "最多改约次数",
  cancel_penalty: "取消订单扣分", cancel_penalty_urgent: "临近交接取消扣分",
  cancel_urgent_hours: "临近交接时限（小时）", order_overtime_hours: "超时未核销关闭（小时）",
  overtime_penalty: "超时扣分", slot_capacity: "单时段容量", storage_days: "交接点暂存天数",
  credit_init: "初始信用分", credit_max: "信用分上限", credit_deal_add: "成交加分",
  credit_good_add: "好评加分", credit_bad_sub: "差评扣分", credit_break_sub: "违约扣分",
  credit_appeal_lose_sub: "申诉败诉扣分", credit_publish_min: "发布信用分下限",
  idle_months_offline: "闲置自动下架（月）", sms_daily_limit: "短信每日上限",
};

const AdminView = {
  template: `
  <div class="container admin-page">
    <div class="spinner" v-if="loading">正在加载…</div>
    <template v-else>
    <header class="page-heading"><div><span class="eyebrow">CARE FOR EVERY CAMPUS CONNECTION</span><h1>让每一次流转，都有序发生。</h1><p>书循管理台 · 教材审核、校园信用与知识循环</p></div><button class="btn ghost small" :disabled="busy" @click="loadAll">刷新数据<ui-icon name="arrow" :size="16"/></button></header>

    <div class="grid grid-4">
      <div class="card"><div class="stat-num">{{ stats.reuse_rate }}%</div><div class="stat-label">教材复用率</div></div>
      <div class="card"><div class="stat-num">¥{{ fmtPrice(stats.saved_amount) }}</div><div class="stat-label">累计节约金额</div></div>
      <div class="card"><div class="stat-num">{{ stats.deals }}</div><div class="stat-label">成交笔数</div></div>
      <div class="card"><div class="stat-num">{{ stats.users }}</div><div class="stat-label">注册用户</div></div>
    </div>

    <div class="nav-tabs">
      <button :class="{active: tab==='audit'}" @click="tab='audit'">内容审核 <span class="tag warn" v-if="pending.books.length + pending.reports.length">{{ pending.books.length + pending.reports.length }}</span></button>
      <button :class="{active: tab==='users'}" @click="tab='users'">用户管理</button>
      <button :class="{active: tab==='params'}" @click="tab='params'">参数配置</button>
      <button :class="{active: tab==='donations'}" @click="tab='donations'">捐赠回收</button>
      <button :class="{active: tab==='logs'}" @click="tab='logs'">操作日志</button>
      <button :class="{active: tab==='rank'}" @click="tab='rank'">统计排行</button>
    </div>

    <!-- 内容审核 -->
    <div class="card" v-if="tab==='audit'">
      <h3>待审核教材</h3>
      <div v-if="!pending.books.length" class="empty">无待审核教材</div>
      <div class="order-item" v-for="b in pending.books" :key="b.id">
        <div class="row"><span><b>{{ b.title }}</b><span class="muted" style="font-size:12px"> · {{ b.author || '作者未知' }}</span></span>
          <span><button class="btn small" :disabled="busy" @click="audit(b.id, true)">通过</button>
          <button class="btn small ghost" :disabled="busy" @click="audit(b.id, false)">驳回</button></span>
        </div>
        <div class="muted" style="font-size:12px">编号 {{ b.isbn }}</div>
      </div>
      <h3 style="margin-top:14px">举报处理</h3>
      <div v-if="!pending.reports.length" class="empty">无待处理举报</div>
      <div class="order-item" v-for="r in pending.reports" :key="r.id">
        <div class="row"><span>{{ TARGET_TEXT[r.target_type] || r.target_type }} #{{ r.target_id }} · <b>{{ r.reason_type }}</b></span>
          <span><button class="btn small ghost" :disabled="busy" @click="handleReport(r.id, false)">仅标记处理</button>
          <button class="btn small" :disabled="busy" @click="handleReport(r.id, true)">下架处理</button></span>
        </div>
        <div class="muted" style="font-size:12px">{{ r.detail }}</div>
      </div>
    </div>

    <!-- 用户管理 -->
    <div class="card" v-if="tab==='users'">
      <div class="row" style="margin-bottom:8px">
        <input v-model="kw" placeholder="搜索姓名 / 学院 / 学号" style="flex:1;height:34px;border-radius:8px;border:1px solid var(--border);padding:0 10px" />
        <span class="muted" style="font-size:12px">共 {{ filteredUsers.length }} 人</span>
      </div>
      <div class="table-wrap">
      <table>
        <tr><th>姓名</th><th>学号</th><th>学院</th><th>角色</th><th>信用分</th><th>状态</th><th>操作</th></tr>
        <tr v-for="u in filteredUsers" :key="u.id">
          <td>{{ u.name }}</td><td>{{ u.student_no }}</td><td>{{ u.college }}</td>
          <td><span class="tag gray">{{ ROLE_TEXT[u.role] || u.role }}</span></td>
          <td>{{ u.credit_score }}<span class="muted" style="font-size:12px">（{{ u.level }}）</span></td>
          <td><span class="tag" :class="u.status==='active' ? '' : 'warn'">{{ USER_STATUS_TEXT[u.status] || u.status }}</span></td>
          <td>
            <button class="btn small ghost" :disabled="busy" @click="toggle(u)">{{ u.status==='active'?'禁用':'启用' }}</button>
            <button class="btn small ghost" :disabled="busy" @click="adjust(u)">调整信用分</button>
            <button class="btn small ghost" :disabled="busy" v-if="u.role==='student'" @click="openCert(u)">认证交接点</button>
          </td>
        </tr>
      </table>
      </div>
    </div>

    <!-- 交接点管理员认证弹窗 -->
    <div class="modal-mask" v-if="cert.show" @click.self="cert.show=false">
      <div class="modal">
        <h3 style="margin-top:0">认证为交接点管理员</h3>
        <div class="field"><label>工号 / 学号（必填）</label>
          <input v-model="cert.student_no" placeholder="如：20230003" />
        </div>
        <div class="field"><label>所属学院</label>
          <input v-model="cert.college" :placeholder="cert.user ? cert.user.college : '留空则沿用该用户学院'" />
        </div>
        <div class="field"><label>绑定交接点（可选）</label>
          <select v-model="cert.point_id">
            <option :value="null">按学院自动创建 / 绑定</option>
            <option v-for="p in certPoints" :key="p.id" :value="p.id">{{ p.name }}（{{ p.college || '通用' }}）</option>
          </select>
        </div>
        <div class="hint muted" style="font-size:12px;margin-bottom:12px">
          认证后该用户将获得交接点核销权限（扫码核销、异常登记）。
        </div>
        <div class="row">
          <button class="btn ghost" @click="cert.show=false">取消</button>
          <button class="btn" :disabled="busy" @click="doCert">{{ busy ? '认证中…' : '确认认证' }}</button>
        </div>
      </div>
    </div>

    <!-- 参数配置 -->
    <div class="card" v-if="tab==='params'">
      <div class="row" style="margin-bottom:8px">
        <div class="muted" style="font-size:12px;flex:1">业务阈值集中配置，保存后立即生效</div>
        <input v-model="paramsKw" placeholder="搜索参数" style="height:32px;width:160px;border-radius:8px;border:1px solid var(--border);padding:0 8px" />
      </div>
      <div v-if="!filteredParams.length" class="empty">无匹配参数</div>
      <div class="order-item" v-for="p in filteredParams" :key="p.key">
        <div><b>{{ PARAM_NAME_TEXT[p.key] || p.key }}</b> <span class="muted" style="font-size:12px"> · {{ p.remark || '无说明' }}</span></div>
        <div class="muted" style="font-size:12px"><span style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace">{{ p.key }}</span> · 默认值 {{ p.default }}</div>
        <div class="row" style="gap:8px;margin-top:6px">
          <input style="height:32px;border-radius:6px;border:1px solid var(--border);width:140px;padding:0 8px" v-model="p.value" />
          <button class="btn small" :disabled="busy" @click="saveParam(p)">保存</button>
          <button class="btn small ghost" :disabled="busy || p.value === p.default" @click="resetParam(p)">恢复默认</button>
        </div>
      </div>
    </div>

    <!-- 捐赠回收 -->
    <div class="card" v-if="tab==='donations'">
      <div class="row" style="margin-bottom:8px">
        <select v-model="donationStatus" style="height:34px;border-radius:8px;border:1px solid var(--border);padding:0 8px">
          <option value="">全部状态</option>
          <option value="pending">待审核</option>
          <option value="approved">已通过</option>
        </select>
        <span class="muted" style="font-size:12px">共 {{ filteredDonations.length }} 条</span>
      </div>
      <div v-if="!filteredDonations.length" class="empty">暂无捐赠记录</div>
      <div class="order-item" v-for="d in filteredDonations" :key="d.id">
        <div class="row"><span><b>{{ d.user }}</b> 捐赠《{{ d.book_title }}》× {{ d.quantity }}</span>
          <span><span class="tag" :class="d.status==='pending'?'warn':''">{{ DONATION_STATUS_TEXT[d.status] || d.status }}</span>
          <button class="btn small" :disabled="busy" v-if="d.status==='pending'" @click="approve(d)">审核通过</button></span></div>
        <div class="muted" style="font-size:12px">{{ d.created_at ? d.created_at.slice(0,10) : '' }} · 受赠人：{{ d.beneficiary || '待分配' }}</div>
      </div>
    </div>

    <!-- 操作日志 -->
    <div class="card" v-if="tab==='logs'">
      <div class="row" style="margin-bottom:8px">
        <select v-model="logAction" style="height:34px;border-radius:8px;border:1px solid var(--border);padding:0 8px">
          <option value="">全部动作</option>
          <option v-for="(t, k) in LOG_ACTION_TEXT" :value="k" :key="k">{{ t }}</option>
        </select>
        <span class="muted" style="font-size:12px">共 {{ filteredLogs.length }} 条</span>
      </div>
      <div class="table-wrap">
      <table>
        <tr><th>时间</th><th>操作人</th><th>动作</th><th>对象</th><th>变更</th><th>IP</th></tr>
        <tr v-for="l in filteredLogs" :key="l.id">
          <td style="white-space:nowrap">{{ l.created_at ? l.created_at.replace('T',' ').slice(0,16) : '' }}</td>
          <td>{{ operatorName(l.operator_id) }}</td>
          <td><span class="tag gray">{{ LOG_ACTION_TEXT[l.action] || l.action }}</span></td>
          <td>{{ l.target }}</td>
          <td class="muted" style="font-size:12px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ l.before ? l.before + ' → ' : '' }}{{ l.after }}</td>
          <td class="muted">{{ l.ip || '—' }}</td>
        </tr>
      </table>
      </div>
    </div>

    <!-- 统计排行 -->
    <div class="card" v-if="tab==='rank'">
      <h3>学院成交排行</h3>
      <div v-if="!stats.college_rank || !stats.college_rank.length" class="empty">暂无数据</div>
      <div class="rank-item" v-for="(r, i) in stats.college_rank" :key="r.college">
        <div class="row" style="margin-bottom:4px"><span><b class="rank-no">{{ i + 1 }}</b>{{ r.college }}</span><b>{{ r.count }} 笔</b></div>
        <div class="bar"><div class="bar-fill" :style="{width: pct(r.count, maxCollege)}"></div></div>
      </div>

      <h3 style="margin-top:16px">热门教材 TOP</h3>
      <div v-if="!stats.hot_books || !stats.hot_books.length" class="empty">暂无数据</div>
      <div class="rank-item" v-for="(b, i) in stats.hot_books" :key="b.book_id">
        <div class="row" style="margin-bottom:4px"><span><b class="rank-no">{{ i + 1 }}</b>{{ b.title }}</span><b>{{ b.deal_count }} 笔</b></div>
        <div class="bar"><div class="bar-fill" :style="{width: pct(b.deal_count, maxHot)}"></div></div>
      </div>

      <h3 style="margin-top:16px">交接点负载</h3>
      <div v-if="!stats.point_load || !stats.point_load.length" class="empty">暂无数据</div>
      <div class="rank-item" v-for="p in stats.point_load" :key="p.point_id">
        <div class="row" style="margin-bottom:4px"><span>{{ p.name }}</span><b>{{ p.deal_count }} 笔 · {{ p.load_rate }}%</b></div>
        <div class="bar"><div class="bar-fill" :style="{width: (p.load_rate > 100 ? 100 : p.load_rate) + '%'}"></div></div>
      </div>

      <h3 style="margin-top:16px">报表导出（Excel）</h3>
      <div class="row" style="gap:8px">
        <button class="btn small" :disabled="busy" @click="exportReport('month')">月报</button>
        <button class="btn small" :disabled="busy" @click="exportReport('quarter')">季报</button>
        <button class="btn small" :disabled="busy" @click="exportReport('term')">学期报</button>
      </div>
    </div>
    </template>

    <!-- 调整信用分弹窗 -->
    <div class="modal-mask" v-if="adjustTarget" @click.self="adjustTarget=null">
      <div class="modal">
        <h3>调整信用分</h3>
        <div class="muted" style="font-size:13px;margin-bottom:10px">用户：{{ adjustTarget.name }}（{{ adjustTarget.student_no }}），当前 {{ adjustTarget.credit_score }} 分</div>
        <div class="field"><label>变动分值（正加负减）</label><input type="number" v-model.number="adjustForm.delta" /></div>
        <div class="field"><label>调整原因</label><input v-model="adjustForm.reason" /></div>
        <div class="row" style="gap:8px;margin-top:8px">
          <button class="btn ghost" style="flex:1" @click="adjustTarget=null">取消</button>
          <button class="btn" style="flex:1" :disabled="busy" @click="doAdjust">确定调整</button>
        </div>
      </div>
    </div>

    <!-- 捐赠审核弹窗 -->
    <div class="modal-mask" v-if="donateTarget" @click.self="donateTarget=null">
      <div class="modal">
        <h3>审核捐赠</h3>
        <div class="muted" style="font-size:13px;margin-bottom:10px">{{ donateTarget.user }} 捐赠《{{ donateTarget.book_title }}》× {{ donateTarget.quantity }}</div>
        <div class="field"><label>受赠人 / 分配去向</label><input v-model="donateForm.beneficiary" placeholder="如：学工部审核名单 / 张同学" /></div>
        <div class="row" style="gap:8px;margin-top:8px">
          <button class="btn ghost" style="flex:1" @click="donateTarget=null">取消</button>
          <button class="btn" style="flex:1" :disabled="busy" @click="doApprove">确定审核</button>
        </div>
      </div>
    </div>
  </div>`,
  setup() {
    const tab = ref("audit");
    const stats = ref({});
    const pending = ref({ books: [], reports: [] });
    const allUsers = ref([]);
    const params = ref([]);
    const donations = ref([]);
    const logs = ref([]);
    const kw = ref("");
    const paramsKw = ref("");
    const donationStatus = ref("");
    const logAction = ref("");
    const loading = ref(false);
    const adjustTarget = ref(null);
    const adjustForm = reactive({ delta: 0, reason: "管理员人工调整" });
    const cert = reactive({ show: false, user: null, student_no: "", college: "", point_id: null });
    const certPoints = ref([]);
    const donateTarget = ref(null);
    const donateForm = reactive({ beneficiary: "" });
    const { busy, run } = useBusy();

    const filteredUsers = computed(() => {
      const q = kw.value.trim().toLowerCase();
      if (!q) return allUsers.value;
      return allUsers.value.filter((u) =>
        (u.name || "").toLowerCase().includes(q) ||
        (u.college || "").toLowerCase().includes(q) ||
        String(u.student_no || "").includes(q)
      );
    });
    const filteredParams = computed(() => {
      const q = paramsKw.value.trim().toLowerCase();
      if (!q) return params.value;
      return params.value.filter((p) =>
        (p.key || "").toLowerCase().includes(q) || (p.remark || "").toLowerCase().includes(q)
      );
    });
    const filteredDonations = computed(() =>
      donationStatus.value ? donations.value.filter((d) => d.status === donationStatus.value) : donations.value
    );
    const filteredLogs = computed(() =>
      logAction.value ? logs.value.filter((l) => l.action === logAction.value) : logs.value
    );
    const maxCollege = computed(() => Math.max(1, ...(stats.value.college_rank || []).map((r) => r.count)));
    const maxHot = computed(() => Math.max(1, ...(stats.value.hot_books || []).map((b) => b.deal_count)));
    function pct(v, max) { return Math.round((v / max) * 100) + "%"; }
    function operatorName(id) {
      const u = allUsers.value.find((x) => x.id === id);
      return u ? u.name : "#" + id;
    }

    async function loadAll() {
      loading.value = true;
      try {
        stats.value = await api("/admin/stats/overview");
        pending.value = await api("/admin/pending");
        donations.value = await api("/admin/donations");
        logs.value = (await api("/admin/logs?size=200")).items;
        params.value = await api("/admin/params");
        allUsers.value = (await api("/admin/users?size=200")).items;
      } catch (e) { setError(e.message); }
      finally { loading.value = false; }
    }
    function audit(id, okv) {
      if (!confirm(okv ? "确认审核通过该教材？" : "确认驳回该教材？")) return;
      return run(async () => {
        await api("/catalog/books/" + id + "/audit?approved=" + okv, { method: "POST" });
        setNotice("已审核"); loadAll();
      }).catch((e) => setError(e.message));
    }
    function handleReport(id, ban) {
      if (!confirm(ban ? "确认下架该内容并标记处理？" : "确认仅标记为已处理？")) return;
      return run(async () => {
        await api("/admin/reports/" + id + "/handle?result=" + (ban ? "已下架" : "已处理") + "&ban=" + ban, { method: "POST" });
        setNotice("已处理"); loadAll();
      }).catch((e) => setError(e.message));
    }
    function toggle(u) {
      const act = u.status === "active" ? "禁用" : "启用";
      if (!confirm("确认" + act + "用户 " + u.name + "？")) return;
      return run(async () => {
        await api("/admin/users/" + u.id + "/status?status=" + (u.status === "active" ? "disabled" : "active"), { method: "POST" });
        setNotice("已" + act); loadAll();
      }).catch((e) => setError(e.message));
    }
    function adjust(u) {
      adjustTarget.value = u;
      adjustForm.delta = 0;
      adjustForm.reason = "管理员人工调整";
    }
    function doAdjust() {
      const u = adjustTarget.value;
      if (!u) return;
      return run(async () => {
        await api("/admin/users/" + u.id + "/credit?delta=" + Number(adjustForm.delta) + "&reason=" + encodeURIComponent(adjustForm.reason), { method: "POST" });
        setNotice("已调整"); adjustTarget.value = null; loadAll();
      }).catch((e) => setError(e.message));
    }
    async function openCert(u) {
      cert.user = u;
      cert.student_no = u.student_no || "";
      cert.college = u.college || "";
      cert.point_id = null;
      cert.show = true;
      try { certPoints.value = await api("/handoff/points"); }
      catch (e) { certPoints.value = []; }
    }
    function doCert() {
      if (!cert.student_no.trim()) return setError("请填写工号/学号");
      return run(async () => {
        await api("/handoff/cert", {
          method: "POST",
          body: { student_no: cert.student_no.trim(), college: cert.college.trim(), point_id: cert.point_id },
        });
        setNotice("已认证为交接点管理员");
        cert.show = false;
        loadAll();
      }).catch((e) => setError(e.message));
    }
    function saveParam(p) {
      return run(async () => {
        await api("/admin/params", { method: "PUT", body: { key: p.key, value: p.value } });
        setNotice("参数已更新");
      }).catch((e) => setError(e.message));
    }
    function resetParam(p) {
      p.value = p.default;
      return saveParam(p);
    }
    function approve(d) {
      donateTarget.value = d;
      donateForm.beneficiary = "";
    }
    function doApprove() {
      const d = donateTarget.value;
      if (!d) return;
      return run(async () => {
        await api("/admin/donations/" + d.id + "/approve?beneficiary=" + encodeURIComponent(donateForm.beneficiary || "待分配"), { method: "POST" });
        setNotice("审核通过"); donateTarget.value = null; loadAll();
      }).catch((e) => setError(e.message));
    }
    async function exportReport(period) {
      try {
        const res = await fetch(API + "/admin/stats/export?period=" + period, {
          headers: { Authorization: "Bearer " + store.token },
        });
        if (!res.ok) throw new Error("导出失败，请稍后重试");
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "report_" + period + ".xlsx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setNotice("报表已导出");
      } catch (e) { setError(e.message); }
    }
    onMounted(loadAll);
    return {
      tab, stats, pending, filteredUsers, kw, params, paramsKw, filteredParams,
      donations, donationStatus, filteredDonations, logs, logAction, filteredLogs,
      loading, busy, adjustTarget, adjustForm, cert, certPoints, donateTarget, donateForm,
      maxCollege, maxHot, pct, operatorName, LOG_ACTION_TEXT, USER_STATUS_TEXT,
      ROLE_TEXT, DONATION_STATUS_TEXT, TARGET_TEXT, PARAM_NAME_TEXT,
      audit, handleReport, toggle, adjust, doAdjust, openCert, doCert,
      saveParam, resetParam, approve, doApprove, exportReport, loadAll,
    };
  },
};
