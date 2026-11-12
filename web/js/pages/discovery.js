function discoverReadingBook(book) {
  go("book/" + book.id);
}

function useBookFavorites() {
  const saved = ref(new Set());
  const favoriteBusy = ref(false);
  async function loadFavorites() {
    if (!store.token) { saved.value = new Set(); return; }
    try {
      const favorites = await api("/search/favorites/mine");
      saved.value = new Set(favorites.map((favorite) => favorite.book_id));
    } catch (error) { setError(error.message); }
  }
  async function toggleFavorite(item) {
    if (!store.token) return requestLogin();
    if (favoriteBusy.value) return;
    favoriteBusy.value = true;
    const exists = saved.value.has(item.book_id);
    try {
      await api("/search/favorites/" + item.book_id, { method: exists ? "DELETE" : "POST" });
      const updated = new Set(saved.value);
      if (exists) updated.delete(item.book_id); else updated.add(item.book_id);
      saved.value = updated;
      setNotice(exists ? "已取消收藏" : "好书已收藏，上架时会提醒你");
    } catch (error) { setError(error.message); }
    finally { favoriteBusy.value = false; }
  }
  onMounted(loadFavorites);
  watch(() => store.token, loadFavorites);
  return { saved, favoriteBusy, toggleFavorite };
}

const READING_GUIDES = [
  { title: "第一次在书循买书？从这里开始", label: "新手指南", image: "library", summary: "找到课程教材，选好交接点，把一份知识接力带回去。", paragraphs: ["在书籍集市搜索书名、作者、书籍编号或课程代码。按课程和成色筛选后，打开书籍详情，比较不同同学的在架货源与价格。书籍编号由平台统一编制，用于识别目录条目。", "选择想要的货源并发起预约，等待卖家确认。在订单中核对约定时间和交接地点，确认后双方可查看联系方式。", "到校内交接点检查教材实物，确认版次、笔记与缺页情况。请交接点管理员使用核销码完成核销，再为本次交易留下评价。"] },
  { title: "旧书定价，怎样让双方都觉得刚刚好", label: "流转课堂", image: "teaching_building", summary: "成色、版次与笔记，都是一本旧书的价值线索。", paragraphs: ["发布前先核对教材书名与版次。同名教材的不同版次可能对应不同课程要求，请选择准确的教材目录。", "已录入定价的教材，平台售价上限为原价的 70%。发布页面会给出参考价格区间，你可以结合成色、笔记情况和市场供给，在范围内设定合适的价格。", "如实拍摄封面、书脊及有笔记的内页，并说明缺页或破损。清楚的描述能减少沟通成本，也能让知识更快找到需要它的人。"] },
  { title: "赴一场有信用的校园之约", label: "安心交接", image: "ginkgo_avenue", summary: "一次如约而至，让下一次相遇也值得期待。", paragraphs: ["请在平台内完成预约，并选择双方都方便的交接点。预约锁定后及时确认，避免影响其他同学找书。", "如需取消，请尽早沟通并通过订单操作。平台会记录履约情况；违约取消会影响信用分，临近交接时取消扣分更高。", "完成交接后 7 日内可进行双向评价。如有货不对板、缺页或未到场等问题，可通过订单提交申诉，等待管理员处理。"] },
];

const DiscoverView = {
  template: `
  <div class="container discover-page">
    <section class="discovery-hero" @mouseenter="paused=true" @mouseleave="paused=false" @focusin="paused=true" @focusout="paused=false" aria-label="书循校园书房">
      <div class="hero-copy">
        <div class="hero-kicker"><span class="status-dot"></span>在成信大，让好书接着读</div>
        <h1><span class="hero-line">知识有来处，</span><span class="hero-line">好书有<span class="hero-emphasis">下一站<svg viewBox="0 0 240 18" aria-hidden="true"><path d="M3 12C62 2 160 2 235 8M28 17C91 8 181 8 222 12"/></svg></span>。</span></h1>
        <p class="hero-description">一本书，连接两段校园时光。<br/>把课堂里的知识传下去，也把书页里的故事留下来。</p>
        <div class="hero-buttons"><a class="btn" href="#/reading">发现我的下一本书 <ui-icon name="diagonal" :size="18"/></a><a class="hero-secondary" href="#/publish">分享一本好书 <ui-icon name="arrow" :size="17"/></a></div>
        <form class="hero-search" @submit.prevent="searchBooks"><ui-icon name="search" :size="20"/><label class="sr-only" for="hero-search">寻找书名、作者或课程</label><input id="hero-search" v-model="heroKeyword" placeholder="这学期，你想读点什么？"/><button type="submit" aria-label="搜索校园好书"><ui-icon name="arrow" :size="20"/></button></form>
        <div class="hero-search-hints"><span>从这里开始</span><a href="#/market?kw=高等数学">高等数学</a><a href="#/market?kw=数据结构">数据结构</a><button @click="openAssistant()">让小循帮我选 <ui-icon name="spark" :size="13"/></button></div>
      </div>
      <div class="hero-art">
        <div class="campus-window"><img v-for="(slide,index) in slides" :key="slide.image" :src="'./assets/campus/'+slide.image+'.webp'" :alt="slide.alt" :class="{visible: currentSlide===index}" :loading="index===0 ? 'eager' : 'lazy'" class="hero-photo"/><span class="campus-window-label"><ui-icon name="pin" :size="14"/>成都信息工程大学</span></div>
        <div class="hero-cycle-badge" aria-hidden="true"><span>旧书 · 新知 · 再相逢</span><b>循</b><ui-icon name="leaf" :size="20"/></div>
        <div class="hero-shelf" v-if="readingItems.length"><span class="hero-shelf-label">好书，正在等下一位读者</span><a v-for="(book,index) in readingItems.slice(0,3)" :key="book.id" :href="'#/book/'+book.id" class="hero-book" v-tilt :style="{'--book-angle': (index-1)*9+'deg'}" :aria-label="'翻开'+book.title"><book-cover :title="book.title" :src="book.cover"/></a></div>
        <div class="hero-photo-caption"><span>校园里，<em>每一本书都有故事。</em></span><span class="hero-photo-index">0{{ currentSlide+1 }} <i>/ 03</i></span></div>
      </div>
      <div class="hero-bottom"><span><span class="hero-caption-line"></span>{{ slides[currentSlide].caption }}</span><div class="hero-controls"><button class="hero-prev" aria-label="上一张校园照片" @click="changeSlide(-1)"><ui-icon name="chevron" :size="16"/></button><button v-for="(slide,index) in slides" :key="index" class="hero-dot" :class="{active: index===currentSlide}" :aria-label="'查看'+slide.alt" :aria-pressed="index===currentSlide" @click="currentSlide=index"></button><button class="hero-next" aria-label="下一张校园照片" @click="changeSlide(1)"><ui-icon name="chevron" :size="16"/></button><button :aria-label="manualPaused ? '播放校园照片轮播' : '暂停校园照片轮播'" :aria-pressed="manualPaused" @click="manualPaused=!manualPaused"><ui-icon :name="manualPaused ? 'play' : 'pause'" :size="15"/></button></div></div>
    </section>

    <nav class="category-shortcuts" v-reveal aria-label="快速发现"><a v-for="(entry,index) in entries" :key="entry.title" :href="entry.href" class="motion-card" v-spotlight><span class="shortcut-number">0{{ index+1 }}</span><span class="shortcut-icon" :class="entry.tone"><ui-icon :name="entry.icon" :size="25"/></span><span class="shortcut-copy"><strong>{{ entry.title }}</strong><small>{{ entry.caption }}</small></span><ui-icon name="diagonal" :size="18" class="shortcut-arrow"/></a></nav>

    <section class="featured-section" v-reveal>
      <header class="section-heading"><div><span class="eyebrow"><span class="section-number">01</span> THE CAMPUS BOOKSHELF</span><h2>从课堂，读到<span class="serif-accent">更大的世界。</span></h2></div><div class="section-actions"><div class="segmented-control" aria-label="书架内容"><button :class="{active: shelfMode==='reading'}" :aria-pressed="shelfMode==='reading'" @click="shelfMode='reading'">校园选书</button><button :class="{active: shelfMode==='sale'}" :aria-pressed="shelfMode==='sale'" @click="shelfMode='sale'">在架好书</button></div><a class="text-link" href="#/market">逛逛集市<ui-icon name="diagonal" :size="17"/></a></div></header>
      <div class="subject-chips" aria-label="按学科选书"><button :class="{active: !selectedCategory}" @click="pickCategory('')">全部方向</button><button v-for="category in categories" :key="category.id" :class="{active: selectedCategory===category.id}" @click="pickCategory(category.id)">{{ category.name }}</button></div>
      <p class="shelf-note" v-if="shelfMode==='reading'"><ui-icon name="book" :size="15"/>真实封面教材目录 · 点击查看详情、在架货源或收藏求购。<a v-if="readingTotal>readingItems.length" :href="'#/reading'+(selectedCategory ? '?category='+selectedCategory : '')">查看全部 {{ readingTotal }} 本<ui-icon name="arrow" :size="14"/></a></p>
      <p class="shelf-note" v-else><ui-icon name="leaf" :size="15"/>{{ total }} 本在架好书 · 每一次流转，都连接着另一位成信同学。</p>
      <div class="book-grid home-book-grid" v-if="shelfLoading"><div class="book-skeleton skel" v-for="number in 4" :key="number"></div></div>
      <div class="empty" v-else-if="shelfError"><p>{{ shelfError }}</p><button class="btn ghost" @click="reloadShelf">重新加载</button></div>
      <div v-else-if="shelfMode==='reading' && readingItems.length" class="book-grid home-book-grid"><reading-card v-for="item in readingItems" :key="item.isbn" :item="item" @discover="findReadingBook"/></div>
      <div v-else-if="shelfMode==='sale' && items.length" class="book-grid home-book-grid"><book-card v-for="item in items" :key="item.id" :item="item" :saved="saved.has(item.book_id)" :busy="favoriteBusy" @open="openBook" @favorite="toggleFavorite"/></div>
      <div v-else class="empty"><h3>这个方向的书架，等你来点亮</h3><p>换个学科看看，或分享你手里的好书。</p><a class="btn" href="#/publish">分享我的一本书</a></div>
    </section>

    <section class="home-companion" v-reveal><div class="companion-card motion-card" v-spotlight><div class="companion-topline"><span class="eyebrow">A LITTLE HELP, A GOOD BOOK</span><span class="companion-badge"><ui-icon name="spark" :size="13"/>小循 AI</span></div><div class="companion-content"><div><h2>还没有头绪？<br/>和小循，<em>聊两句。</em></h2><p>从你的课程、兴趣和预算出发，<br/>一起找找书循里值得翻开的那一本。</p><button class="btn" @click="openAssistant()">让小循陪我选书<ui-icon name="arrow" :size="17"/></button></div><div class="companion-orbit" aria-hidden="true"><span class="orbit-line"></span><span class="orbit-line second"></span><ui-icon name="spark" :size="62"/><span class="orbit-label">FIND YOUR NEXT READ</span></div></div><div class="companion-prompts"><button @click="openAssistant()"><ui-icon name="cap" :size="16"/>对上这学期的课表<ui-icon name="diagonal" :size="13"/></button><button @click="openAssistant()"><ui-icon name="leaf" :size="16"/>读一点课堂之外<ui-icon name="diagonal" :size="13"/></button></div></div><a class="campus-postcard" href="#/about"><img src="./assets/campus/bell_tower.webp" alt="成信大校园钟楼" loading="lazy"/><span class="postcard-top">POSTCARD FROM CUIT <ui-icon name="diagonal" :size="18"/></span><div><span class="eyebrow">书页之外，身边的世界</span><h2>我们在同一个校园，<br/>也在同一本书里相遇。</h2><span class="text-link">认识书循 <ui-icon name="arrow" :size="17"/></span></div></a></section>

    <a class="circulation-banner" v-reveal href="#/activities"><img src="./assets/campus/ginkgo_avenue.webp" alt="秋日银杏大道" loading="lazy"/><div class="circulation-shade"></div><div><span class="eyebrow">PASS IT ON / 教材循环计划</span><h2>这一程读完，<br class="mobile-break"/>下一程<span>接力。</span></h2><p>把不再需要的书，留给正在需要它的人。</p></div><span class="banner-round-arrow"><ui-icon name="diagonal" :size="28"/></span></a>

    <section class="guides-section" v-reveal><header class="section-heading"><div><span class="eyebrow"><span class="section-number">02</span> LIFE BETWEEN THE PAGES</span><h2>慢一点，<span class="serif-accent">读读校园。</span></h2></div><a class="text-link" href="#/news">阅读全部<ui-icon name="diagonal" :size="17"/></a></header><div class="guide-grid"><a class="guide-card" v-for="(guide,index) in guides" :key="guide.title" :href="'#/news?article='+index"><div class="guide-image"><img :src="'./assets/campus/'+guide.image+'.webp'" :alt="guide.title" loading="lazy"/><span class="guide-index">0{{ index+1 }}</span></div><div><span>{{ guide.label }}</span><h3>{{ guide.title }}</h3><p>{{ guide.summary }}</p><span class="guide-read">读一读<ui-icon name="diagonal" :size="16"/></span></div></a></div></section>
    <div class="trust-strip"><span><ui-icon name="shield"/>同校流转，安心相遇</span><span><ui-icon name="pin"/>校内交接，当面验书</span><span><ui-icon name="leaf"/>一本旧书，一份新知</span><span><ui-icon name="heart"/>如实描述，真诚相待</span></div>
  </div>`,
  setup() {
    const items = ref([]);
    const total = ref(0);
    const sort = ref("view_desc");
    const shelfMode = ref("reading");
    const categories = ref([]);
    const selectedCategory = ref("");
    const readingItems = ref([]);
    const readingTotal = ref(0);
    const readingLoading = ref(true);
    const readingError = ref("");
    const loading = ref(true);
    const loadError = ref("");
    const currentSlide = ref(0);
    const paused = ref(false);
    const manualPaused = ref(false);
    const heroKeyword = ref("");
    function searchBooks() { go("market" + (heroKeyword.value.trim() ? "?kw=" + encodeURIComponent(heroKeyword.value.trim()) : "")); }
    const slides = [
      { image: "library", alt: "成都信息工程大学图书馆", caption: "CAMPUS MOMENTS / 校园里的书香" },
      { image: "teaching_building", alt: "成都信息工程大学教学楼", caption: "CAMPUS MOMENTS / 走过熟悉的校园" },
      { image: "ginkgo_avenue", alt: "成都信息工程大学银杏大道", caption: "CAMPUS MOMENTS / 把故事留在秋天" },
    ];
    const entries = [
      { title: "分类选书", caption: "从兴趣出发，发现好书", icon: "book", tone: "green", href: "#/reading" },
      { title: "课程找书", caption: "对上课表，找到对的书", icon: "cap", tone: "gold", href: "#/market?mode=course" },
      { title: "好书捐赠", caption: "让分享成为一种日常", icon: "leaf", tone: "sage", href: "#/activities" },
      { title: "校园互助", caption: "约在校园，传递书香", icon: "hands", tone: "blue", href: "#/points" },
    ];
    const favorites = useBookFavorites();
    let sequence = 0;
    let readingSequence = 0;
    const shelfLoading = computed(() => shelfMode.value === "reading" ? readingLoading.value : loading.value);
    const shelfError = computed(() => shelfMode.value === "reading" ? readingError.value : loadError.value);
    async function loadReading() {
      const request = ++readingSequence;
      readingLoading.value = true;
      readingError.value = "";
      try {
        const response = await api("/catalog/cover-library?size=4&category=" + selectedCategory.value);
        if (request !== readingSequence) return;
        readingItems.value = response.items;
        readingTotal.value = response.total;
      } catch (error) { if (request === readingSequence) readingError.value = "选书书单暂时没有加载成功，请稍后重试。"; }
      finally { if (request === readingSequence) readingLoading.value = false; }
    }
    function pickCategory(value) { selectedCategory.value = value; loadReading(); loadBooks(); }
    function reloadShelf() { return shelfMode.value === "reading" ? loadReading() : loadBooks(); }
    async function loadBooks() {
      const request = ++sequence;
      loading.value = true;
      loadError.value = "";
      try {
        const response = await api("/search?size=4&sort=" + sort.value + "&category=" + selectedCategory.value);
        if (request !== sequence) return;
        items.value = response.items;
        total.value = response.total;
      } catch (error) { if (request === sequence) loadError.value = "好书暂时没有加载成功，请稍后重试。"; }
      finally { if (request === sequence) loading.value = false; }
    }
    function changeSort(value) { sort.value = value; loadBooks(); }
    function changeSlide(delta) { currentSlide.value = (currentSlide.value + delta + slides.length) % slides.length; }
    function openBook(item) { go("book/" + item.book_id + "?listing=" + item.id); }
    let slideTimer;
    onMounted(() => {
      loadBooks();
      loadReading();
      api("/catalog/facets").then(data => { categories.value = data.categories.filter(category => category.cover_count || category.count); }).catch(error => setError(error.message));
      if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        slideTimer = setInterval(() => { if (!paused.value && !manualPaused.value && !document.hidden) changeSlide(1); }, 8000);
      }
    });
    onUnmounted(() => { clearInterval(slideTimer); sequence++; readingSequence++; });
    return { items, total, sort, loading, loadError, currentSlide, paused, manualPaused, heroKeyword, searchBooks, openAssistant, slides, entries, guides: READING_GUIDES, ...favorites, loadBooks, changeSort, changeSlide, openBook, shelfMode, categories, selectedCategory, readingItems, readingTotal, shelfLoading, shelfError, pickCategory, reloadShelf, findReadingBook: discoverReadingBook };
  },
};

const ReadingView = {
  template: `
  <div class="container reading-page">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13"/><span>校园选书</span></div>
    <header class="page-heading"><div><span class="eyebrow">ONE CAMPUS, MANY STORIES</span><h1>每一种好奇，都有一本书回应。</h1><p>从一门课，到一种兴趣；从一本书，认识另一个成信同学。</p></div><a class="text-link" href="#/market">去看在架好书<ui-icon name="arrow" :size="17"/></a></header>
    <div class="subject-chips" aria-label="选择书籍学科"><button :class="{active: !category}" @click="pickCategory('')">全部方向</button><button v-for="option in categories" :key="option.id" :class="{active: category===option.id}" @click="pickCategory(option.id)">{{ option.name }}</button></div>
    <div class="reading-toolbar"><p class="shelf-note">真实封面教材目录 · {{ total }} 本校园好书</p><form class="reading-search" @submit.prevent="load(true)"><ui-icon name="search" :size="17"/><input type="search" aria-label="搜索教材目录" v-model="keyword" @input="onInput" placeholder="按书名或 13 位书籍编号查找"/><button class="text-button" type="submit">查找</button></form></div>
    <p class="reference-note"><ui-icon name="book" :size="17"/>书籍已录入教材目录，编号由书循统一顺序编制。目录封面供选书参考，实物版次、价格和成色以卖家挂牌为准；暂无货源时可收藏或发布求购。</p>
    <div class="book-grid home-book-grid" v-if="loading && !books.length"><div class="book-skeleton skel" v-for="number in 8" :key="number"></div></div>
    <div v-else-if="error" class="empty"><p>{{ error }}</p><button class="btn ghost" @click="load(true)">重新加载</button></div>
    <div v-else-if="books.length" class="book-grid home-book-grid"><reading-card v-for="book in books" :key="book.isbn" :item="book" @discover="findReadingBook"/></div>
    <div v-else class="empty"><ui-icon name="search" :size="32"/><h2>这个书架，还在等待新的故事</h2><p>换个关键词，或去集市看看同学们正在分享的书。</p><button class="btn ghost" @click="clearFilters">查看全部书单</button></div>
    <div class="market-bottom"><span>把知识接力，也把校园记忆留下来。</span><button class="btn ghost" v-if="books.length<total" :disabled="loading" @click="load(false)">{{ loading ? '加载中…' : '继续发现好书' }}<ui-icon name="arrow" :size="16"/></button><span v-else-if="books.length">已展示全部 {{ total }} 本</span></div>
  </div>`,
  setup() {
    const books = ref([]);
    const total = ref(0);
    const categories = ref([]);
    const category = ref("");
    const keyword = ref("");
    const loading = ref(true);
    const error = ref("");
    let page = 1;
    let loadedFilters = "";
    let sequence = 0;
    let timer;
    let disposed = false;
    async function load(reset = true) {
      if (disposed || (!reset && loading.value)) return;
      clearTimeout(timer);
      const searchKeyword = keyword.value.trim();
      const requestedFilters = JSON.stringify([category.value, searchKeyword]);
      if (requestedFilters !== loadedFilters) reset = true;
      const request = ++sequence;
      const requestedPage = reset ? 1 : page + 1;
      const query = new URLSearchParams();
      if (category.value) query.set("category", category.value);
      if (searchKeyword) query.set("kw", searchKeyword);
      history.replaceState(null, "", location.pathname + location.search + "#/reading" + (query.size ? "?" + query : ""));
      query.delete("kw");
      query.set("keyword", searchKeyword);
      query.set("page", requestedPage);
      query.set("size", 12);
      loading.value = true;
      error.value = "";
      try {
        const result = await api("/catalog/cover-library?" + query);
        if (request !== sequence) return;
        books.value = reset ? result.items : books.value.concat(result.items);
        total.value = result.total;
        page = requestedPage;
        loadedFilters = requestedFilters;
      } catch (failure) { if (request === sequence) error.value = "书单暂时没有加载成功，请稍后重试。"; }
      finally { if (request === sequence) loading.value = false; }
    }
    function pickCategory(value) { category.value = value; books.value = []; load(); }
    function clearFilters() { category.value = ""; keyword.value = ""; load(); }
    function onInput() { clearTimeout(timer); timer = setTimeout(() => load(), 300); }
    function restoreFilters(params) { if (disposed) return; category.value = params.category || ""; keyword.value = params.kw || ""; load(); }
    onMounted(() => {
      api("/catalog/facets").then(result => { if (!disposed) categories.value = result.categories.filter(option => option.cover_count); }).catch(failure => setError(failure.message));
      restoreFilters(store.route.params);
    });
    watch(() => store.route.params, restoreFilters);
    onUnmounted(() => { disposed = true; sequence++; clearTimeout(timer); });
    return { books, total, categories, category, keyword, loading, error, load, pickCategory, clearFilters, onInput, findReadingBook: discoverReadingBook };
  },
};
