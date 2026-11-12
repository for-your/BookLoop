/* ---------------- 组件：首页（搜索 + 列表） ---------------- */
const MarketView = {
  template: `
  <div class="container market-page">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13" /><span>书籍集市</span></div>
    <header class="market-intro" v-reveal><div><span class="eyebrow">THE SECONDHAND BOOK CLUB</span><h1>好书不贵，<span>相遇刚好。</span></h1><p>从一门课、一种兴趣出发，找到同学书架上属于你的下一本。</p></div><a href="#/reading" class="market-catalog-link"><ui-icon name="book" :size="29"/><span>还没找到？<b>翻翻校园教材目录</b></span><ui-icon name="diagonal" :size="20"/></a></header>
    <div class="market-layout">
      <aside class="market-sidebar" :class="{expanded: sheetOpen}" aria-label="筛选在架书籍">
        <div class="sidebar-heading"><h2><ui-icon name="book" :size="18" />按学科找书</h2><button class="icon-button mobile-only" aria-label="关闭筛选" @click="sheetOpen=false"><ui-icon name="close" /></button></div>
        <button class="category-option" :class="{active: !categoryId}" @click="pickCategory('')"><ui-icon name="grid" :size="16" />全部学科</button>
        <button class="category-option" v-for="category in categories" :key="category.id" :class="{active: categoryId===category.id}" @click="pickCategory(category.id)">{{ category.name }}<ui-icon name="chevron" :size="13"/></button>
        <div class="sidebar-section"><h3>按开课学院</h3><select aria-label="开课学院" v-model="collegeFilter" @change="pickCollege"><option value="">全部学院</option><option v-for="college in colleges" :key="college.name" :value="college.name">{{ college.name }}</option></select><p class="filter-help">依据课程归属筛选，通识教材可跨学院选用。</p></div>
        <div class="sidebar-section"><h3>按课程</h3><select aria-label="课程筛选" v-model="courseId" @change="applyFilters"><option value="">全部课程</option><option v-for="course in filteredCourses" :key="course.id" :value="course.id">{{ course.name }}</option></select></div>
        <div class="sidebar-section"><h3>成色筛选</h3><select aria-label="成色筛选" v-model="condition" @change="applyFilters"><option value="">全部成色</option><option v-for="value in conditions" :key="value">{{ value }}</option></select></div>
        <div class="sidebar-section"><h3>价格区间</h3><div class="price-range"><input aria-label="最低价" type="number" min="0" placeholder="¥ 最低" v-model.number="minPrice" @input="onPriceInput"/><span>—</span><input aria-label="最高价" type="number" min="0" placeholder="¥ 最高" v-model.number="maxPrice" @input="onPriceInput"/></div></div>
        <div class="sidebar-section" v-if="points.length"><h3>交接地点</h3><select aria-label="交接地点" v-model="pointId" @change="applyFilters"><option value="">全部交接点</option><option v-for="point in points" :key="point.id" :value="point.id">{{ point.name }}</option></select></div>
        <div class="sidebar-note"><ui-icon name="leaf" :size="25"/><p>旧书不闲置<br/>知识有回响</p><span>让校园里的每一份知识<br/>都找到新的归属。</span></div>
        <button class="btn ghost full-width" v-if="hasFilters" @click="clearFilters">清除全部筛选</button>
      </aside>
      <section class="market-results">
        <p class="reference-note" v-if="referenceIsbn"><ui-icon name="book" :size="17"/>购买前请与卖家核对书名、版次和实物照片。书籍编号为平台统一编制的检索编号。</p>
        <header class="section-heading market-heading"><div><span class="eyebrow">CAMPUS BOOK MARKET</span><h1>书籍集市 <small>共 {{ total }} 本在架好书</small></h1></div><button class="text-button" @click="openWanted"><ui-icon name="plus" :size="16"/>发布求购</button></header>
        <div class="market-toolbar"><div class="toolbar-description"><ui-icon name="shield" :size="16"/><span>同校交易 · 当面交接</span></div><button class="btn ghost small mobile-only" @click="sheetOpen=!sheetOpen"><ui-icon name="filter" :size="16"/>筛选 {{ filterCount || '' }}</button><select aria-label="排序方式" v-model="sort" @change="applyFilters"><option value="time_desc">最新发布</option><option value="view_desc">热度优先</option><option value="price_asc">价格从低到高</option><option value="price_desc">价格从高到低</option></select></div>
        <div class="active-filters" v-if="hasFilters"><span>{{ filterSummary || '已选择交接点' }}</span><button class="text-button" @click="clearFilters">清除筛选 <ui-icon name="close" :size="13"/></button></div>
        <div class="book-grid market-grid" v-if="loading && !items.length"><div class="book-skeleton skel" v-for="number in 6" :key="number"></div></div>
        <div v-else-if="!items.length" class="empty market-empty"><ui-icon name="search" :size="38"/><h3>这本好书，还在来的路上</h3><p>试试其他关键词，或发布求购，让有书的同学找到你。</p><div class="empty-actions"><button class="btn ghost" @click="clearFilters">浏览全部</button><button class="btn" @click="openWanted">发布求购</button></div></div>
        <div v-else class="book-grid market-grid" :class="{'is-loading': loading}"><book-card v-for="item in items" :key="item.id" :item="item" :saved="favIds.has(item.book_id)" :busy="favBusy" @open="go('book/'+$event.book_id+'?listing='+$event.id)" @favorite="toggleFav" /></div>
        <div class="market-bottom"><span>每一次流转，都是知识的延续。</span><button v-if="hasMore" class="btn ghost" :disabled="loading" @click="loadMore">{{ loading ? '加载中…' : '再看看更多好书' }}<ui-icon name="arrow" :size="16" /></button><span v-else-if="items.length">已展示全部 {{ total }} 本</span></div>
      </section>
    </div>

    <!-- 求购弹窗 -->
    <div class="modal-mask" v-if="wanted.show" @click.self="wanted.show=false">
      <div class="modal">
        <h3 style="margin-top:0">发布求购</h3>
        <div class="field"><label>教材（书名 / 书籍编号检索）</label>
          <input v-model="wanted.kw" @input="onWantedInput" placeholder="如：数据结构 或 0000000000001" />
        </div>
        <div v-if="wanted.books.length && !wanted.picked" class="card" style="margin-top:8px;padding:6px;max-height:220px;overflow-y:auto">
          <div v-for="b in wanted.books" :key="b.id" class="row" style="padding:6px 4px;border-bottom:1px solid var(--border);cursor:pointer" @click="wanted.picked=b">
            <span style="font-size:13px">{{ b.title }}</span><span class="muted" style="font-size:12px">¥{{ b.price }}</span>
          </div>
        </div>
        <div v-if="wanted.picked" class="hint" style="margin:8px 0">
          已选择：《{{ wanted.picked.title }}》
          <a href="#" style="margin-left:6px" @click.prevent="wanted.picked=null">重选</a>
        </div>
        <div class="grid grid-2 keep" style="margin-top:8px">
          <div class="field"><label>成色下限</label>
            <select v-model="wanted.min_condition"><option v-for="c in conditions" :key="c" :value="c">{{ c }}</option></select>
          </div>
          <div class="field"><label>心理价位（¥）</label>
            <input type="number" v-model.number="wanted.max_price" placeholder="0 表示不限" />
          </div>
        </div>
        <div class="row" style="margin-top:12px">
          <button class="btn ghost" @click="wanted.show=false">取消</button>
          <button class="btn" :disabled="busy || !wanted.picked" @click="submitWanted">{{ busy ? '提交中…' : '发布求购' }}</button>
        </div>
      </div>
    </div>
  </div>`,
  setup() {
    const items = ref([]);
    const courses = ref([]);
    const conditions = ref([]);
    const total = ref(0);
    const courseId = ref("");
    const categoryId = ref("");
    const categories = ref([]);
    const colleges = ref([]);
    const referenceIsbn = ref("");
    const condition = ref("");
    const minPrice = ref(null);
    const maxPrice = ref(null);
    const sort = ref("time_desc");
    const collegeFilter = ref("");
    const filteredCourses = computed(() => courses.value.filter(course => !collegeFilter.value || course.college === collegeFilter.value));
    const points = ref([]);
    const pointId = ref("");
    const loading = ref(false);
    const page = ref(1);
    const size = 20;
    const hasMore = ref(false);
    const { busy, run } = useBusy();
    let searchSequence = 0;
    let disposed = false;

    /* ---- 零结果出口：清除筛选 / 发布求购 ---- */
    const hasFilters = computed(() =>
      !!(store.keyword || categoryId.value || courseId.value || condition.value || (minPrice.value !== null && minPrice.value !== "") || (maxPrice.value !== null && maxPrice.value !== "") || collegeFilter.value || pointId.value)
    );
    function clearFilters() {
      store.keyword = ""; courseId.value = ""; condition.value = "";
      minPrice.value = null; maxPrice.value = null; collegeFilter.value = "";
      categoryId.value = ""; referenceIsbn.value = "";
      pointId.value = "";
      sort.value = "time_desc";
      load();
    }

    /* ---- URL 同步：筛选条件写进 hash，链接可直接分享 ---- */
    function syncHash() {
      const q = new URLSearchParams();
      if (store.keyword) q.set("kw", store.keyword);
      if (courseId.value) q.set("course", courseId.value);
      if (categoryId.value) q.set("category", categoryId.value);
      if (referenceIsbn.value) q.set("reference", referenceIsbn.value);
      if (condition.value) q.set("cond", condition.value);
      if (minPrice.value !== null && minPrice.value !== "") q.set("min", minPrice.value);
      if (maxPrice.value !== null && maxPrice.value !== "") q.set("max", maxPrice.value);
      if (pointId.value) q.set("point", pointId.value);
      if (collegeFilter.value) q.set("college", collegeFilter.value);
      if (sort.value !== "time_desc") q.set("sort", sort.value);
      const qs = q.toString();
      history.replaceState(null, "", location.pathname + location.search + "#/market" + (qs ? "?" + qs : ""));
    }

    /* ---- 桌面端筛选即筛：成色/排序 change 立即，价格输入防抖 500ms ---- */
    let priceTimer = null;
    function applyFilters() { return load(); }
    function onPriceInput() {
      clearTimeout(priceTimer);
      priceTimer = setTimeout(applyFilters, 500);
    }

    /* ---- 已选条件徽标与摘要（移动端入口用） ---- */
    const filterCount = computed(() => {
      let n = 0;
      if (store.keyword) n++;
      if (categoryId.value) n++;
      if (courseId.value) n++;
      if (condition.value) n++;
      if (minPrice.value !== null && minPrice.value !== "") n++;
      if (maxPrice.value !== null && maxPrice.value !== "") n++;
      if (collegeFilter.value) n++;
      if (pointId.value) n++;
      if (sort.value !== "time_desc") n++;
      return n;
    });
    const filterSummary = computed(() => {
      const parts = [];
      if (store.keyword) parts.push(store.keyword);
      if (categoryId.value) parts.push(categories.value.find(category => category.id === categoryId.value)?.name || "指定学科");
      if (courseId.value) {
        const c = courses.value.find((x) => x.id === courseId.value);
        if (c) parts.push(c.name);
      }
      if (collegeFilter.value) parts.push(collegeFilter.value);
      if (pointId.value) parts.push(points.value.find((point) => point.id === pointId.value)?.name || "指定交接点");
      if (condition.value) parts.push(condition.value);
      if ((minPrice.value !== null && minPrice.value !== "") || (maxPrice.value !== null && maxPrice.value !== "")) parts.push("¥" + (minPrice.value || 0) + "-" + (maxPrice.value === null || maxPrice.value === "" ? "∞" : maxPrice.value));
      if (parts.length) return parts.join(" · ");
      return "";
    });

    const sheetOpen = ref(false);
    function closeDesktopSheet() { if (window.innerWidth > 768) sheetOpen.value = false; }

    /* ---- 求购弹窗：搜书 → 选书 → 出价 ---- */
    const wanted = reactive({ show: false, kw: "", books: [], picked: null, min_condition: "有破损", max_price: 0 });
    let wTimer = null;
    function openWanted() {
      if (!store.token) return requestLogin(location.hash.slice(2) + (location.hash.includes("?") ? "&" : "?") + "wanted=1");
      wanted.show = true; wanted.picked = null; wanted.kw = store.keyword || "";
      if (wanted.kw) searchWantedBooks();
    }
    function onWantedInput() { clearTimeout(wTimer); wTimer = setTimeout(searchWantedBooks, 300); }
    async function searchWantedBooks() {
      if (!wanted.kw.trim()) { wanted.books = []; return; }
      try {
        const d = await api("/catalog/books?keyword=" + encodeURIComponent(wanted.kw) + "&size=6");
        wanted.books = d.items || [];
      } catch (e) { wanted.books = []; }
    }
    function submitWanted() {
      if (!wanted.picked) return setError("请先选择要求购的教材");
      return run(async () => {
        await api("/listings/wanted", {
          method: "POST",
          body: { book_id: wanted.picked.id, min_condition: wanted.min_condition, max_price: Number(wanted.max_price) || 0 },
        });
        wanted.show = false;
        setNotice("求购已发布，有人上架时将提醒你");
      }).catch((e) => setError(e.message));
    }

    async function fetchPage(reset) {
      const request = ++searchSequence;
      if (reset) page.value = 1;
      const qs = new URLSearchParams();
      if (courseId.value) qs.set("course_id", courseId.value);
      if (categoryId.value) qs.set("category", categoryId.value);
      if (pointId.value) qs.set("point_id", pointId.value);
      if (store.keyword) qs.set("keyword", store.keyword);
      if (condition.value) qs.set("condition", condition.value);
      if (minPrice.value !== null && minPrice.value !== "") qs.set("min_price", minPrice.value);
      if (maxPrice.value !== null && maxPrice.value !== "") qs.set("max_price", maxPrice.value);
      if (collegeFilter.value) qs.set("course_college", collegeFilter.value);
      qs.set("sort", sort.value);
      qs.set("page", page.value);
      qs.set("size", size);
      loading.value = true;
      try {
        const d = await api("/search?" + qs.toString());
        if (request !== searchSequence) return;
        items.value = reset ? d.items : items.value.concat(d.items);
        total.value = d.total;
        hasMore.value = items.value.length < d.total;
      } catch (e) { if (request === searchSequence) setError(e.message); }
      finally { if (request === searchSequence) loading.value = false; }
    }
    function load() { if (disposed) return; syncHash(); return fetchPage(true); }
    function loadMore() { if (loading.value) return; page.value++; return fetchPage(false); }
    function loadByCourse() { return load(); }

    /* ---- 卡片收藏：悬浮心形，登录后按 book_id 收藏 / 取消 ---- */
    const favIds = ref(new Set());
    const favBusy = ref(false);
    async function loadFavs() {
      if (!store.token) return;
      try {
        const favs = await api("/search/favorites/mine");
        favIds.value = new Set(favs.map((f) => f.book_id));
      } catch (e) { /* 未登录或加载失败不打扰浏览 */ }
    }
    function toggleFav(l) {
      if (!store.token) return requestLogin();
      if (favBusy.value) return;
      const on = favIds.value.has(l.book_id);
      favBusy.value = true;
      return (async () => {
        try {
          if (on) await api("/search/favorites/" + l.book_id, { method: "DELETE" });
          else await api("/search/favorites/" + l.book_id, { method: "POST" });
          const next = new Set(favIds.value);
          on ? next.delete(l.book_id) : next.add(l.book_id);
          favIds.value = next;
          setNotice(on ? "已取消收藏" : "已收藏，有货源将提醒你");
        } catch (e) { setError(e.message); }
        finally { favBusy.value = false; }
      })();
    }
    function pickCourse(c) {
      courseId.value = c.id;
      loadByCourse();
    }
    function pickCategory(value) { categoryId.value = value; courseId.value = ""; load(); }
    function pickCollege() {
      if (courseId.value && !filteredCourses.value.some(course => course.id === courseId.value)) courseId.value = "";
      load();
    }
    let restoring = false;
    function restoreFilters(params) {
      if (disposed) return;
      restoring = true;
      clearTimeout(kwTimer);
      store.keyword = params.kw || "";
      condition.value = params.cond || "";
      minPrice.value = params.min !== undefined ? Number(params.min) : null;
      maxPrice.value = params.max !== undefined ? Number(params.max) : null;
      collegeFilter.value = params.college || "";
      categoryId.value = params.category || "";
      referenceIsbn.value = params.reference || "";
      sort.value = params.sort || "time_desc";
      courseId.value = params.course ? Number(params.course) : "";
      pointId.value = params.point ? Number(params.point) : "";
      load();
      nextTick(() => { restoring = false; });
    }
    onMounted(async () => {
      window.addEventListener("resize", closeDesktopSheet);
      try {
        courses.value = await api("/catalog/courses");
        conditions.value = await api("/search/conditions");
        const facets = await api("/catalog/facets");
        categories.value = facets.categories.filter(category => category.count || category.cover_count);
        colleges.value = facets.colleges;
        if (store.token) points.value = await api("/handoff/points");
      } catch (e) {}
      if (disposed) return;
      loadFavs();
      restoreFilters(store.route.params);
      if (store.route.params.wanted) openWanted();
    });
    // 关键词 300ms 防抖：打字过程中不连续请求
    let kwTimer = null;
    watch(() => store.keyword, () => {
      if (restoring) return;
      clearTimeout(kwTimer);
      kwTimer = setTimeout(() => { courseId.value = ""; load(); }, 300);
    });
    watch(() => store.route.params, restoreFilters);
    onUnmounted(() => { disposed = true; window.removeEventListener("resize", closeDesktopSheet); clearTimeout(kwTimer); clearTimeout(priceTimer); clearTimeout(wTimer); searchSequence++; });
    return { items, total, courses, conditions, courseId, condition, minPrice, maxPrice, sort, collegeFilter, points, pointId, loading, hasMore, busy,
             categoryId, categories, colleges, filteredCourses, referenceIsbn, pickCategory, pickCollege,
             hasFilters, clearFilters, wanted, openWanted, onWantedInput, submitWanted,
             filterCount, filterSummary, sheetOpen,
             applyFilters, onPriceInput,
             favIds, favBusy, toggleFav, pickCourse,
             load, loadMore, loadByCourse, go };
  },
};
