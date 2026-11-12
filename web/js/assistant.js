const assistantState = reactive({ open: false, bookId: null, bookTitle: "" });

function openAssistant(book = null) {
  assistantState.bookId = book?.id || (store.route.name === "book" ? Number(store.route.params.id) || null : null);
  assistantState.bookTitle = book?.title || (assistantState.bookId ? "当前浏览的书籍" : "");
  assistantState.open = true;
}

const AssistantPanel = {
  template: `
    <button v-if="!state.open" class="assistant-launcher" @click="openAssistant()" aria-label="打开小循选书助手" aria-haspopup="dialog" aria-controls="assistant-panel"><span class="assistant-launcher-icon"><ui-icon name="spark" :size="22"/></span><span>问问小循<small>选书有个伴</small></span></button>
    <div v-if="state.open" class="modal-mask assistant-mask" @click.self="state.open=false">
      <section id="assistant-panel" class="modal assistant-panel" role="dialog" aria-modal="true" aria-labelledby="assistant-title">
        <header class="assistant-header"><div class="assistant-identity"><span class="assistant-mark"><ui-icon name="leaf" :size="25"/></span><div><h2 id="assistant-title">小循 <span>AI 选书助手</span></h2><p>陪你找书，也陪好书找到下一站</p></div></div><div class="assistant-controls"><button class="icon-button" aria-label="开启新对话，清空当前记录" title="新对话" :disabled="!turns.length" @click="reset"><ui-icon name="plus" :size="19"/></button><button class="icon-button" aria-label="关闭小循选书助手" @click="state.open=false"><ui-icon name="close" :size="20"/></button></div></header>
        <div class="assistant-scroll" ref="scrollArea">
          <div v-if="!turns.length" class="assistant-welcome">
            <span class="assistant-eyebrow">一本书 · 一段新的相遇</span><h3>下一本好书，<br/><span>一起找。</span></h3><p>告诉我课程、兴趣或预算，<br/>从书循的真实书目里，找一找适合你的选择。</p>
            <div class="assistant-starters"><button v-for="(starter,index) in starters" :key="starter.question" :disabled="!ready || busy" @click="send(starter.question)"><span class="assistant-starter-number">0{{ index+1 }}</span><ui-icon :name="starter.icon" :size="21"/><b>{{ starter.title }}</b><small>{{ starter.description }}</small><ui-icon name="arrow" :size="16"/></button></div>
            <div class="assistant-welcome-note"><ui-icon name="book" :size="17"/><p>可以继续说“换个方向”或“预算再少一点”。<br/>具体课程用书，请以老师要求的版次为准。</p></div>
          </div>
          <div class="assistant-conversation" v-if="turns.length" role="log" aria-live="polite" aria-relevant="additions text">
            <article class="assistant-turn" v-for="turn in turns" :key="turn.id">
              <div class="assistant-user"><span>你</span><p>{{ turn.question }}</p></div>
              <div class="assistant-response"><div class="assistant-speaker"><ui-icon name="leaf" :size="16"/><b>小循</b><span v-if="turn.response">陪你选一本好书</span></div>
                <template v-if="turn.response">
                  <p class="assistant-model-note" v-if="turn.response.model!==turn.request.model">所选模型暂忙，本次由 {{ turn.response.model }} 回答。</p>
                  <p class="assistant-answer">{{ turn.response.answer }}</p>
                  <div v-if="turn.response.books.length" class="assistant-books">
                    <a v-for="book in turn.response.books" :key="book.id" :href="'#/book/'+book.id" @click="state.open=false" :aria-label="'查看 '+book.title">
                      <book-cover :title="book.title" :src="book.cover"/>
                      <div><span class="assistant-category">{{ book.category_name }}</span><h4>{{ book.title }}</h4><p>{{ book.edition || '版次请核对实物' }}</p>
                        <span v-if="book.on_sale_count && book.min_price != null" class="assistant-book-price">¥{{ fmtPrice(book.min_price) }}<small>起 · {{ book.on_sale_count }} 个在架货源</small></span>
                        <span v-else class="assistant-no-stock">暂无在架 · 可收藏求购</span>
                      </div><ui-icon name="chevron" :size="16"/>
                    </a>
                  </div>
                  <details class="assistant-source"><summary>依据平台公开资料 · {{ checkedTime(turn.response.checked_at) }} 核对</summary><p>本次参考 {{ turn.response.catalog_count }} 本候选书目、课程关联、在架信息和当前交易规则。价格与货源可能变动，请在详情页核对；成色以卖家实物和当面验书为准。回答模型：{{ turn.response.model }}。</p></details>
                  <div class="assistant-followups" v-if="turn===turns.at(-1)"><button v-for="question in turn.response.suggestions" :key="question" :disabled="!ready || busy" @click="send(question)">{{ question }}<ui-icon name="arrow" :size="13"/></button></div>
                </template>
                <div v-else-if="busy && turn.id===activeTurnId" class="assistant-thinking" role="status"><span><i></i><i></i><i></i></span><p>正在翻阅目录，整理适合你的选择…</p><small v-if="takingLong">这次稍久一些，你可以停止等待后重新提问。</small></div>
                <div v-else-if="turn.error" class="assistant-error" role="alert"><p>{{ turn.error }}</p><button class="text-button" :disabled="busy || !ready" @click="runTurn(turn)">重新回答 <ui-icon name="arrow" :size="14"/></button><a href="#/market" @click="state.open=false">先去集市看看</a></div>
              </div>
            </article>
          </div>
        </div>
        <div class="assistant-offline" v-if="statusError || (configuration && !configuration.enabled)" role="status"><p>{{ statusError || '小循还未连接 AI 服务，请联系管理员配置。你也可以先去集市按课程找书。' }}</p><button v-if="statusError" class="text-button" @click="loadStatus">重新连接</button><a href="#/market?mode=course" @click="state.open=false">课程找书 <ui-icon name="arrow" :size="13"/></a></div>
        <form class="assistant-composer" @submit.prevent="send()"><div v-if="state.bookId" class="assistant-context"><ui-icon name="book" :size="14"/><span>正在聊：{{ state.bookTitle }}</span><button type="button" class="icon-button" aria-label="移除当前书籍上下文" @click="state.bookId=null;state.bookTitle=''">×</button></div><label class="sr-only" for="assistant-input">告诉小循你的课程、兴趣或预算</label><textarea id="assistant-input" data-dialog-focus ref="inputArea" v-model="draft" :disabled="!ready" :placeholder="ready ? '例如：预算 30 元，想找一本数据结构教材…' : configuration ? '暂时无法提问' : '正在连接小循…'" rows="2" maxlength="1000" @keydown="handleKey"></textarea><div class="assistant-composer-bar"><span>Enter 发送 · Shift + Enter 换行</span><span class="assistant-input-count" v-if="draft.length > 800">{{ draft.length }}/1000</span><button v-if="busy" type="button" class="assistant-send stop" @click="stopWaiting" aria-label="停止等待回答"><span class="assistant-stop-icon"></span>停止等待</button><button v-else type="submit" class="assistant-send" :disabled="!ready || !draft.trim()" aria-label="发送给小循"><ui-icon name="arrow" :size="18"/></button></div></form>
        <footer class="assistant-footnote"><span>AI 建议仅供参考 · 对话仅留在当前页面</span><label v-if="configuration?.models?.length > 1">模型<select aria-label="选择小循使用的 AI 模型" v-model="selectedModel" :disabled="busy"><option v-for="model in configuration.models" :key="model" :value="model">{{ model }}</option></select></label><span v-else-if="configuration?.model">{{ configuration.model }}</span></footer>
        <p class="assistant-privacy">提问和公开书目会发送至 AI 服务，请勿输入个人联系方式或密码。</p>
      </section>
    </div>`,
  setup() {
    const state = assistantState;
    const turns = ref([]);
    const draft = ref("");
    const configuration = ref(null);
    const statusError = ref("");
    const selectedModel = ref("");
    const busy = ref(false);
    const activeTurnId = ref(null);
    const takingLong = ref(false);
    const scrollArea = ref(null);
    const inputArea = ref(null);
    const ready = computed(() => !!configuration.value?.enabled);
    let controller = null;
    let turnSequence = 0;
    let focusBeforeOpen = null;
    const starters = computed(() => [
      state.bookId
        ? { icon: "book", title: "聊聊这本书", description: "课程、版次与选购建议", question: "帮我看看当前这本书，关联什么课程？选购时要核对什么？" }
        : { icon: "cap", title: "按课程找教材", description: "说说专业和这学期的课", question: "我是计算机专业，想找数据结构相关教材，有什么可选？" },
      { icon: "search", title: "预算内挑好书", description: "适合自己的，也要实惠", question: "预算30元，有哪些在架教材值得看看？请说明推荐理由。" },
      { icon: "leaf", title: "课外读点什么", description: "让阅读不止于课堂", question: "想在课余读点人文类的书，目录里有什么推荐？" },
      { icon: "hands", title: "让旧书接着发光", description: "发布、求购与校园交接", question: "第一次在书循卖旧教材，怎么定价、发布和交接？" },
    ]);

    async function loadStatus() {
      statusError.value = "";
      try {
        configuration.value = await api("/assistant/status");
        if (!configuration.value.models.includes(selectedModel.value)) selectedModel.value = configuration.value.model;
      } catch (error) {
        statusError.value = "暂时连接不上小循，请稍后再试。";
      }
    }
    async function scrollDown() {
      await nextTick();
      if (scrollArea.value) scrollArea.value.scrollTop = scrollArea.value.scrollHeight;
    }
    function history() {
      const messages = turns.value.filter(turn => turn.response).flatMap(turn => [
        { role: "user", content: turn.question }, { role: "assistant", content: turn.response.answer, book_ids: turn.response.books.map(book => book.id) },
      ]).slice(-8);
      while (messages.reduce((total, message) => total + message.content.length, 0) > 6000) messages.splice(0, 2);
      return messages;
    }
    function send(question) {
      const content = (typeof question === "string" ? question : draft.value).trim();
      if (busy.value || !ready.value || !content || content.length > 1000) return;
      const turn = {
        id: ++turnSequence, question: content, response: null, error: "",
        request: { message: content, history: history(), book_id: state.bookId, model: selectedModel.value },
      };
      turns.value.push(turn);
      draft.value = "";
      runTurn(turns.value.at(-1));
      nextTick(() => inputArea.value?.focus());
    }
    async function runTurn(turn) {
      if (busy.value || !ready.value) return;
      busy.value = true;
      activeTurnId.value = turn.id;
      turn.error = "";
      takingLong.value = false;
      const active = new AbortController();
      controller = active;
      turn.request.model = selectedModel.value;
      const longTimer = setTimeout(() => { takingLong.value = true; }, 10000);
      const timeout = setTimeout(() => active.abort(), (configuration.value.request_timeout_seconds || 55) * 1000);
      scrollDown();
      try {
        const response = await fetch(API + "/assistant/chat", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(turn.request), signal: active.signal,
        });
        const envelope = await response.json();
        if (!response.ok || envelope.code !== 0) throw new Error(envelope.msg || "问题未能提交，请缩短后重试。");
        if (!active.signal.aborted) turn.response = envelope.data;
      } catch (error) {
        if (!turn.error) turn.error = active.signal.aborted ? "等待已结束。可以重新回答，或把问题说得更简短一些。" : error instanceof TypeError ? "网络暂时不畅，请检查连接后重新回答。" : error.message;
      } finally {
        clearTimeout(longTimer);
        clearTimeout(timeout);
        if (controller === active) {
          controller = null;
          busy.value = false;
          activeTurnId.value = null;
          takingLong.value = false;
          scrollDown();
        }
      }
    }
    function stopWaiting() {
      const turn = turns.value.find(item => item.id === activeTurnId.value);
      if (turn && busy.value) turn.error = "已停止等待。你可以修改问题，或重新回答。";
      controller?.abort();
    }
    function reset() {
      controller?.abort();
      controller = null;
      busy.value = false;
      activeTurnId.value = null;
      takingLong.value = false;
      turns.value = [];
      draft.value = "";
      nextTick(() => inputArea.value?.focus());
    }
    function handleKey(event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
        event.preventDefault();
        send();
      }
    }
    function checkedTime(value) {
      return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    }
    watch(() => state.open, async (open) => {
      if (open) {
        focusBeforeOpen = document.activeElement;
        if (!configuration.value || statusError.value) await loadStatus();
        scrollDown();
        await nextTick();
        if (state.open) (ready.value ? inputArea.value : document.querySelector('#assistant-panel'))?.focus();
      } else {
        await nextTick();
        requestAnimationFrame(() => {
          const target = focusBeforeOpen?.isConnected && focusBeforeOpen.matches('button, a[href], input, select, textarea, [tabindex]') ? focusBeforeOpen : document.querySelector('.assistant-launcher');
          target?.focus();
        });
      }
    });
    onUnmounted(() => controller?.abort());
    return { state, turns, draft, configuration, statusError, selectedModel, busy, activeTurnId, takingLong, scrollArea, inputArea,
      ready, starters, openAssistant, loadStatus, send, runTurn, stopWaiting, reset, handleKey, checkedTime, fmtPrice };
  },
};
