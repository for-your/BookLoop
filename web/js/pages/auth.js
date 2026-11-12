/* ---------------- 组件：登录 ---------------- */
const LoginView = {
  template: `
  <div class="container auth-page">
    <section class="auth-story"><span class="eyebrow">A NEW CHAPTER STARTS HERE</span><h1>再翻开，<br/>又是新的故事。</h1><p>你需要的知识，也许就藏在<br/>另一位同学翻过的书页里。</p><span class="auth-caption"><ui-icon name="pin" :size="15"/>成都信息工程大学 · 图书馆</span></section>
    <div class="card auth-card">
      <div class="brand-head">
        <div class="logo-badge"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M9 9h6M9 13h4"/></svg></div>
        <h3>欢迎来到书循</h3>
        <p>登录，让好书与你相遇</p>
      </div>
      <div class="nav-tabs">
        <button :class="{active: tab==='pwd'}" @click="tab='pwd'">学号密码</button>
        <button :class="{active: tab==='code'}" @click="tab='code'">手机验证码</button>
        <button :class="{active: tab==='wechat'}" @click="tab='wechat'">微信</button>
        <button :class="{active: tab==='reg'}" @click="tab='reg'">注册</button>
      </div>

      <form v-if="tab==='pwd'" @submit.prevent="loginPwd">
        <div class="field"><label for="login-student">学号 / 工号</label><input id="login-student" autocomplete="username" v-model="form.student_no" placeholder="请输入学号或工号" required /></div>
        <div class="field"><label for="login-password">密码</label><input id="login-password" type="password" autocomplete="current-password" v-model="form.password" placeholder="请输入密码" required /></div>
<label class="muted" style="font-size:12px"><input type="checkbox" v-model="agree" /> 我已阅读并同意</label><a href="./user-agreement.html" target="_blank" style="font-size:12px">《用户协议》</a>
        <button type="submit" class="btn" style="width:100%;margin-top:12px" :disabled="!agree">开启我的书循之旅 <ui-icon name="arrow" :size="17"/></button>
        <div class="hint muted" style="margin-top:10px;font-size:12px">
          演示账号：学生 20230001 / campus@2026，交接点管理员 T2023001 / campus@2026，平台管理员 admin / admin@2026
        </div>
      </form>

      <div v-else-if="tab==='code'">
        <div class="field"><label>手机号</label><input v-model="form.phone" placeholder="请输入手机号" /></div>
        <div class="field"><label>验证码</label>
          <div style="display:flex;gap:8px">
            <input v-model="form.code" placeholder="6 位验证码" />
            <button class="btn ghost" style="white-space:nowrap" :disabled="codeCd>0" @click="sendCode">{{ codeCd>0 ? codeCd+'s 后重发' : '获取验证码' }}</button>
          </div>
          <div class="hint">演示环境验证码：888888</div>
        </div>
        <button class="btn" style="width:100%" @click="loginCode">登录</button>
      </div>

      <div v-else-if="tab==='wechat'">
        <template v-if="!wxNeedBind">
          <div class="hint muted" style="font-size:12px;margin-bottom:10px">
            微信扫码免密登录（需先绑定微信）。演示环境：填 <code>demo</code> 以演示账号免密登录；填其它任意串模拟「未绑定 → 微信注册」。
          </div>
          <div class="field"><label>微信授权码 code</label><input v-model="wxCode" placeholder="演示填 demo" /></div>
          <button class="btn" style="width:100%" @click="loginWechat">微信登录</button>
        </template>
        <template v-else>
          <div class="hint" style="margin-bottom:10px">该微信尚未绑定账号，请绑定学号创建账号</div>
          <div class="field"><label>学号</label><input v-model="wxReg.student_no" /></div>
          <div class="field"><label>姓名</label><input v-model="wxReg.name" /></div>
          <div class="field"><label>手机号</label><input v-model="wxReg.phone" /></div>
          <div class="field"><label>学院</label><input v-model="wxReg.college" placeholder="如：计算机学院" /></div>
          <div class="field"><label>密码</label><input type="password" v-model="wxReg.password" /></div>
          <button class="btn" style="width:100%" @click="wxRegister">注册并绑定微信</button>
          <a href="#" style="display:block;text-align:center;margin-top:10px;font-size:12px" @click.prevent="wxNeedBind=false">返回重新扫码</a>
        </template>
      </div>

      <div v-else>
        <div class="field"><label>学号</label><input v-model="reg.student_no" /></div>
        <div class="field"><label>姓名</label><input v-model="reg.name" /></div>
        <div class="field"><label>手机号</label><input v-model="reg.phone" /></div>
        <div class="field"><label>学院</label><input v-model="reg.college" placeholder="如：计算机学院" /></div>
        <div class="field"><label>密码</label><input type="password" v-model="reg.password" /></div>
        <button class="btn" style="width:100%" @click="register">注册</button>
      </div>
    </div>
  </div>`,
  setup() {
    const tab = ref("pwd");
    const agree = ref(false);
    const codeCd = ref(0);
    let codeTimer = null;
    const form = reactive({ student_no: "20230001", password: "", phone: "", code: "" });
    const reg = reactive({ student_no: "", name: "", phone: "", college: "", password: "", role: "student" });
    const wxCode = ref("demo");
    const wxNeedBind = ref(false);
    const wxToken = ref("");
    const wxReg = reactive({ student_no: "", name: "", phone: "", college: "", password: "" });

    async function afterLogin(data) {
      store.token = data.access_token;
      localStorage.setItem("cbc_token", data.access_token);
      store.user = data.user;
      setNotice("欢迎回来，" + data.user.nickname);
      const destination = sessionStorage.getItem("bookloop_return");
      sessionStorage.removeItem("bookloop_return");
      go(destination && !destination.startsWith("login") ? destination : "home");
    }
    async function loginPwd() {
      try { afterLogin(await api("/auth/login", { method: "POST", body: { student_no: form.student_no, password: form.password } })); }
      catch (e) { setError(e.message); }
    }
    async function loginCode() {
      try { afterLogin(await api("/auth/login", { method: "POST", body: { phone: form.phone, code: form.code } })); }
      catch (e) { setError(e.message); }
    }
    async function loginWechat() {
      try {
        const d = await api("/auth/wechat/login-url");
        if (!d.mock) { location.href = d.url; return; }
        const r = await api("/auth/wechat/login?code=" + encodeURIComponent(wxCode.value || "demo"), { method: "POST" });
        if (r.need_bind) {
          wxNeedBind.value = true;
          wxToken.value = r.wechat_token;
          setNotice("请绑定学号创建账号");
        } else {
          afterLogin(r);
        }
      } catch (e) { setError(e.message); }
    }
    async function wxRegister() {
      try {
        afterLogin(await api("/auth/wechat/register", { method: "POST", body: { wechat_token: wxToken.value, ...wxReg } }));
      } catch (e) { setError(e.message); }
    }
    async function sendCode() {
      if (codeCd.value > 0) return;
      try {
        await api("/auth/send-code?phone=" + form.phone, { method: "POST" });
        setNotice("验证码已发送（演示：888888）");
        codeCd.value = 60;
        codeTimer = setInterval(() => {
          codeCd.value -= 1;
          if (codeCd.value <= 0) { clearInterval(codeTimer); codeTimer = null; }
        }, 1000);
      } catch (e) { setError(e.message); }
    }
    onUnmounted(() => { if (codeTimer) clearInterval(codeTimer); });
    onMounted(() => {
      const pending = localStorage.getItem("cbc_wx_pending");
      if (pending) {
        try {
          const p = JSON.parse(pending);
          wxToken.value = p.token;
          wxNeedBind.value = true;
          tab.value = "wechat";
        } catch (e) {}
        localStorage.removeItem("cbc_wx_pending");
      }
    });
    async function register() {
      try {
        await api("/auth/register", { method: "POST", body: reg });
        setNotice("注册成功，请登录");
        tab.value = "pwd";
        form.student_no = reg.student_no;
      } catch (e) { setError(e.message); }
    }
    return { tab, agree, codeCd, form, reg, wxCode, wxNeedBind, wxReg, loginPwd, loginCode, loginWechat, wxRegister, sendCode, register };
  },
};
