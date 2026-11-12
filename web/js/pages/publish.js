/* ---------------- 组件：发布 ---------------- */
const PublishView = {
  template: `
  <div class="container publish-page">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13"/><span>发布书籍</span></div>
    <header class="page-heading"><div><span class="eyebrow">LET YOUR BOOK START A NEW JOURNEY</span><h1>分享一本书，续写一段故事。</h1><p>认真描述，让下一位读者更安心地遇见它。</p></div><div class="publish-steps"><span><b>1</b>拍下好书</span><span><b>2</b>完善信息</span><span><b>3</b>等待相遇</span></div></header>
    <div class="card publish-form-layout">
      <aside class="publish-upload-column"><h2 class="publish-section-title"><ui-icon name="camera" :size="18"/>给你的书拍张照</h2><label class="upload-zone"><ui-icon name="camera" :size="38"/><strong>{{ busy ? '正在上传…' : '点击上传实物照片' }}</strong><span>JPG / PNG / WebP · 单张不超过 5MB</span><input type="file" aria-label="上传书籍实物照片" accept="image/jpeg,image/png,image/webp" multiple @change="upload" :disabled="busy"/></label><div class="thumb-list"><div class="thumb" v-for="(image,index) in form.images" :key="image"><img :src="image" :alt="'实物照片 '+(index+1)"/><button class="del" type="button" :aria-label="'移除照片 '+(index+1)" @click="removeImg(index)">×</button></div></div><div class="upload-guide"><ui-icon name="spark" :size="17"/><p>拍一拍封面、书脊和内页。<br/>真实清晰的照片，能让好书更快找到新主人。</p></div><p class="hint">已上传 {{ form.images.length }} 张 · 至少需要 1 张</p></aside>
      <section class="publish-fields"><h2 class="publish-section-title"><ui-icon name="book" :size="18"/>写下这本书的故事</h2>
      <div class="field">
        <label for="publish-book">选择教材 · 书名 / 书籍编号</label>
        <input id="publish-book" v-model="kw" @input="onKwInput" placeholder="搜索教材目录，核对书籍编号和实物版次" autocomplete="off" />
        <div class="hint">{{ selected ? '已选择：《'+selected.title+'》'+(selected.price > 0 ? '定价 ¥'+fmtPrice(selected.price) : '，目录原价待补充') : '未选择教材' }}</div>
        <div v-if="books.length" class="search-results">
          <button v-for="book in books" :key="book.id" @click="pick(book)">{{ book.title }}<small>编号 {{ book.isbn }} · {{ book.price > 0 ? '原价 ¥'+book.price : '原价待补充' }}</small></button>
        </div>
      </div>

      <div class="grid grid-2 keep">
        <div class="field"><label for="publish-condition">书籍成色</label>
          <select id="publish-condition" v-model="form.condition_level"><option v-for="c in conditions" :key="c" :value="c">{{ c }}</option></select>
        </div>
        <div class="field"><label for="publish-price">转让价格（元）</label>
          <input id="publish-price" type="number" min="0" step="0.01" :max="selected?.price > 0 ? suggest.max : undefined" v-model.number="form.price" />
          <div class="hint" v-if="suggest.max">建议区间 ¥{{ fmtPrice(suggest.min) }} ~ ¥{{ fmtPrice(suggest.max) }}</div>
        </div>
      </div>

      <div class="field"><label>交接点（必填）</label>
        <div class="row" style="gap:8px">
          <select v-model="form.point_id" style="flex:1;min-width:0">
            <option v-for="p in points" :key="p.id" :value="p.id">{{ p.name }}（{{ p.location }}）{{ p.mine ? '· 自定义' : '' }}</option>
          </select>
          <button class="btn small ghost" type="button" style="flex:0 0 auto" @click="showPoint=true">＋ 自定义</button>
        </div>
        <div class="hint">没有合适的？可自定义一个仅自己可见的交接点（如宿舍楼下）。</div>
      </div>

      <div class="field"><label for="publish-remark">使用情况与书页里的故事（{{ form.remark.length }}/200）</label><textarea id="publish-remark" v-model="form.remark" maxlength="200" placeholder="如实说明使用情况，也可以分享这本书陪你度过的课程或校园片段。"></textarea></div>
      <div class="publish-checks"><label><input type="checkbox" v-model="form.has_notes"/>有笔记 / 标注</label><label><input type="checkbox" v-model="form.missing_pages"/>存在缺页</label><label><input type="checkbox" v-model="form.negotiable"/>可以议价</label></div>

      <button class="btn full-width" :disabled="busy" @click="submit">{{ busy ? '正在发布…' : '发布这本书，等待新的相遇' }}<ui-icon name="arrow" :size="17"/></button><p class="hint">售价不超过原价 70%。请如实描述，保留交接核销记录。</p>
      </section>
    </div>

    <div class="modal-mask" v-if="showPoint" @click.self="showPoint=false">
      <div class="modal">
        <h3 style="margin-top:0">自定义交接点</h3>
        <div class="field"><label>名称（必填）</label>
          <input v-model="np.name" maxlength="40" placeholder="如：3 号宿舍楼门口" />
        </div>
        <div class="field"><label>位置描述</label>
          <input v-model="np.location" maxlength="120" placeholder="如：东区 3 号楼一层门厅" />
        </div>
        <div class="grid grid-2 keep">
          <div class="field"><label>开放时间</label><input type="time" v-model="np.open_time" /></div>
          <div class="field"><label>关闭时间</label><input type="time" v-model="np.close_time" /></div>
        </div>
        <div class="hint muted" style="font-size:12px;margin-bottom:12px">
          自定义交接点仅你自己可见，发布时可选用；交接仍需在平台核销。最多 5 个。
        </div>
        <div class="row">
          <button class="btn ghost" @click="showPoint=false">取消</button>
          <button class="btn" :disabled="busy" @click="createPoint">{{ busy ? '创建中…' : '创建并使用' }}</button>
        </div>
      </div>
    </div>
  </div>`,
  setup() {
    const kw = ref("");
    const books = ref([]);
    const selected = ref(null);
    const suggest = ref({});
    const conditions = ref([]);
    const points = ref([]);
    const showPoint = ref(false);
    const np = reactive({ name: "", location: "", open_time: "08:00", close_time: "20:00" });
    const form = reactive({
      condition_level: "九成新", price: 0, point_id: null, remark: "",
      has_notes: false, missing_pages: false, negotiable: true, images: [],
    });

    const { busy, run } = useBusy();
    let kwTimer = null;
    let catalogSequence = 0;
    function onKwInput() { catalogSequence++; selected.value = null; suggest.value = {}; books.value = []; clearTimeout(kwTimer); kwTimer = setTimeout(searchBook, 300); }
    function removeImg(i) { form.images.splice(i, 1); }
    async function searchBook() {
      if (!kw.value) { books.value = []; return; }
      const request = ++catalogSequence;
      try {
        const d = await api("/catalog/books?keyword=" + encodeURIComponent(kw.value));
        if (request !== catalogSequence) return;
        books.value = d.items.slice(0, 8);
      } catch (e) { setError(e.message); }
    }
    async function pick(b) {
      clearTimeout(kwTimer);
      const request = ++catalogSequence;
      selected.value = b; books.value = []; kw.value = b.title;
      try {
        const result = await api("/listings/price-suggest?book_id=" + b.id);
        if (request !== catalogSequence) return;
        suggest.value = result;
        form.price = result.max;
      }
      catch (e) { setError(e.message); }
    }
    function upload(e) {
      return run(async () => {
        const files = Array.from(e.target.files || []);
        let uploaded = 0;
        for (const f of files) {
          if (!/\.(jpe?g|png|webp)$/i.test(f.name) || f.size > 5 * 1024 * 1024) {
            setError("请选择不超过 5MB 的 JPG、PNG 或 WebP 图片");
            continue;
          }
          const fd = new FormData(); fd.append("file", f);
          try { const d = await apiForm("/upload", fd); form.images.push(d.url); uploaded++; }
          catch (err) { setError(err.message); }
        }
        e.target.value = "";
        if (uploaded) setNotice("已上传 " + uploaded + " 张实物照片");
      });
    }
    function submit() {
      if (!selected.value) return setError("请先选择教材");
      if (!form.images.length) return setError("请至少上传 1 张实物照片");
      if (!form.point_id) return setError("请选择交接点");
      if (!Number.isFinite(form.price) || form.price < 0) return setError("请填写有效的转让价格");
      if (selected.value.price > 0 && form.price > selected.value.price * 0.7) return setError("转让价格不能超过原价的 70%");
      return run(async () => {
        const d = await api("/listings", {
          method: "POST",
          body: { book_id: selected.value.id, condition_level: form.condition_level, price: form.price,
                  point_id: form.point_id, remark: form.remark, has_notes: form.has_notes,
                  missing_pages: form.missing_pages, negotiable: form.negotiable, images: form.images },
        });
        setNotice(d.matched_wanted ? `发布成功，已匹配 ${d.matched_wanted} 条求购` : "发布成功");
        go("me");
      }).catch((e) => setError(e.message));
    }
    function createPoint() {
      if (!np.name.trim()) return setError("请填写交接点名称");
      return run(async () => {
        const p = await api("/handoff/points/mine", { method: "POST", body: { ...np, name: np.name.trim() } });
        points.value = await api("/handoff/points");
        form.point_id = p.id;
        showPoint.value = false;
        np.name = ""; np.location = "";
        setNotice("已创建自定义交接点《" + p.name + "》");
      }).catch((e) => setError(e.message));
    }
    onMounted(async () => {
      try {
        conditions.value = await api("/search/conditions");
        points.value = await api("/handoff/points");
        if (points.value.length) form.point_id = points.value[0].id;
      } catch (e) { setError(e.message); }
    });
    onUnmounted(() => { clearTimeout(kwTimer); catalogSequence++; });
    return { kw, books, selected, suggest, conditions, points, form, busy, showPoint, np,
             onKwInput, removeImg, searchBook, pick, upload, submit, createPoint, go };
  },
};
