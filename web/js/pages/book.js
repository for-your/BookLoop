/* ---------------- 组件：教材详情 ---------------- */
const BookView = {
  template: `
  <div class="container book-detail">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13"/><a href="#/market">书籍集市</a><ui-icon name="chevron" :size="13"/><span>书籍详情</span></div>
    <div v-if="!book.id && !loadFailed" class="spinner">正在翻开这本书…</div>
    <div v-if="loadFailed" class="empty"><h2>暂时无法打开这本书</h2><p>书籍可能已下架，或网络暂时不可用。</p><button class="btn" @click="go('market')">返回集市</button></div>
    <section class="detail-layout" v-if="book.id">
      <div class="detail-gallery"><div class="detail-cover-stage"><book-cover :title="book.title" :src="selectedImage || selectedListing?.images?.[0] || book.cover || ''" :fallback-src="book.cover || ''" :edition="book.edition" :caption="selectedListing?.images?.length ? '卖家实物照片' : '教材目录封面'"/></div><div class="gallery-thumbnails" v-if="selectedListing?.images?.length > 1"><button v-for="image in selectedListing.images" :key="image" :class="{active: selectedImage===image}" @click="selectedImage=image" aria-label="查看实物照片"><book-cover :title="book.title" :src="image"/></button></div><p class="hint">目录封面供选书参考，请以卖家实物照片核对书名、版次与成色。</p></div>
      <div class="detail-info"><span class="eyebrow">ANOTHER READER, ANOTHER CHAPTER</span><h1>{{ book.title }}</h1><div class="detail-tags"><span class="tag">{{ selectedListing?.condition_level || '教材目录' }}</span><span class="tag warm" v-if="selectedListing?.negotiable">可以议价</span><span class="tag gray" v-if="selectedListing?.has_notes">有笔记 / 标注</span></div><div class="detail-price"><strong v-if="selectedListing"><small>¥</small>{{ fmtPrice(selectedListing.price) }}</strong><strong v-else class="no-stock">暂无在架货源</strong><div><del v-if="selectedListing && book.price > 0">原价 ¥{{ fmtPrice(book.price) }}</del><span v-if="selectedListing && book.price > selectedListing.price">比原价省 ¥{{ fmtPrice(book.price - selectedListing.price) }}</span></div></div><dl class="book-metadata"><div><dt>作者</dt><dd>{{ book.author || '未填写' }}</dd></div><div><dt>出版社</dt><dd>{{ book.publisher || '未填写' }}</dd></div><div><dt>版次</dt><dd>{{ book.edition || '未填写' }}</dd></div><div><dt>书籍编号</dt><dd>{{ book.isbn }}</dd></div><div><dt>适用课程</dt><dd>{{ (book.courses || []).map(course => course.name).join('、') || '暂无关联课程' }}</dd></div></dl><div class="detail-remark" v-if="selectedListing?.remark"><ui-icon name="message" :size="17"/><p>{{ selectedListing.remark }}</p></div><p class="detail-promise"><ui-icon name="leaf" :size="16"/>知识在流转，书香有回响。</p></div>
      <aside class="seller-card" v-if="selectedListing"><div class="seller-identity"><span class="avatar large">{{ (selectedListing.seller_name || '同学').slice(-2,-1) || '书' }}</span><div><h3>{{ selectedListing.seller_name }}</h3><span>{{ selectedListing.seller_college || '校园书友' }}</span></div></div><h4>交接信息</h4><p><ui-icon name="pin" :size="16"/>{{ selectedListing.point_name || '校内交接点' }}</p><p><ui-icon name="shield" :size="16"/>平台预约 · 当面核销</p><p><ui-icon name="clock" :size="16"/>双方确认后约定交接时间</p><button class="btn full-width" :disabled="busy || ownListing" @click="reserveListing(selectedListing)">{{ ownListing ? '这是你发布的书' : busy ? '正在预约…' : '预约这本书' }}<ui-icon name="arrow" :size="16"/></button><button class="btn ghost full-width" :disabled="busy" @click="toggleFav"><ui-icon name="heart" :size="17"/>{{ fav ? '已加入我的收藏' : '收藏这本书' }}</button><small>预约确认后，可在订单中查看双方联系方式。请通过平台核销完成交接。</small></aside>
      <aside class="seller-card" v-if="!selectedListing"><ui-icon name="heart" :size="30"/><h3>{{ listings.length ? '请选择一个在架货源' : '好书值得等待' }}</h3><p>{{ listings.length ? '原先选择的货源已无法预约，请在下方选择其他同学发布的书。' : '先收藏这本书。有同学发布货源时，我们会通过站内消息提醒你。' }}</p><button class="btn ghost full-width" :disabled="busy" @click="toggleFav"><ui-icon name="heart" :size="17"/>{{ fav ? '已加入我的收藏' : '收藏，等好书上架' }}</button><small>也可以发布求购，留下成色要求与预算。</small></aside>
    </section>
    <button v-if="book.id" class="detail-assistant-entry" @click="openAssistant(book)"><span><ui-icon name="spark" :size="21"/></span><div><b>这本书，适合我吗？</b><small>问问小循，了解课程关联与选购要点</small></div><ui-icon name="arrow" :size="18"/></button>
    <div class="detail-bottom-grid" v-if="book.id"><section class="card source-card"><div class="section-heading"><h2>同一本书，不同的故事 <small>{{ listings.length }} 个在架货源</small></h2></div><div v-if="loading" class="spinner">正在寻找货源…</div><div v-else-if="!listings.length" class="empty">暂时没有同学发布这本书，试试右侧的求购吧。</div><div v-for="listing in listings" :key="listing.id" class="source-row" :class="{selected: selectedListing?.id===listing.id}"><span class="mini-avatar">{{ (listing.seller_name || '同学').slice(-2,-1) }}</span><div class="source-owner"><b>{{ listing.seller_name }}</b><span>{{ listing.condition_level }} · {{ listing.point_name }}</span></div><strong>¥{{ fmtPrice(listing.price) }}</strong><button class="btn small ghost" @click="selectedListingId=listing.id;selectedImage=''">{{ selectedListing?.id===listing.id ? '已选择' : '看看这本' }}</button></div></section><section class="card wanted-card"><ui-icon name="message" :size="25"/><h2>没找到心仪的成色？</h2><p>留下一份求购，有同学上架时通知你。</p><label class="field"><span>成色要求</span><select v-model="w.min_condition"><option v-for="value in conditions" :key="value">{{ value }}</option></select></label><label class="field"><span>最高预算（元）</span><input type="number" min="0" v-model.number="w.max_price" placeholder="0 表示不限"/></label><button class="btn ghost full-width" :disabled="busy" @click="submitWanted">发布我的求购</button></section></div>
    <div class="detail-cta" v-if="book.id"><button class="btn ghost" :disabled="busy" @click="toggleFav"><ui-icon name="heart" :size="18"/>{{ fav ? '已收藏' : '收藏' }}</button><button v-if="selectedListing" class="btn cta-btn" :disabled="busy || ownListing" @click="reserveListing(selectedListing)">{{ ownListing ? '我的发布' : '预约这本书 · ¥'+fmtPrice(selectedListing.price) }}</button></div>
  </div>`,
  setup() {
    const book = ref({});
    const fav = ref(false);
    const conditions = ref([]);
    const listings = ref([]);
    const loading = ref(false);
    const coverErr = ref(false);
    const loadFailed = ref(false);
    const selectedImage = ref("");
    const selectedListingId = ref(Number(store.route.params.listing) || null);
    const w = reactive({ min_condition: "有破损", max_price: 0 });
    const id = computed(() => store.route.params.id);
    const isLoggedIn = computed(() => !!store.token);
    const cheapest = computed(() => listings.value[0] || null);
    const selectedListing = computed(() => selectedListingId.value ? listings.value.find((listing) => listing.id === selectedListingId.value) || null : cheapest.value);
    const ownListing = computed(() => !!selectedListing.value && selectedListing.value.seller_id === store.user?.id);

    async function loadListings() {
      loading.value = true;
      try {
        const [d, requested] = await Promise.all([
          api("/search?keyword=" + encodeURIComponent(book.value.isbn) + "&sort=price_asc&size=50"),
          selectedListingId.value ? api("/search/" + selectedListingId.value).catch(() => null) : null,
        ]);
        listings.value = d.items || [];
        if (requested?.book_id === book.value.id && requested.status === "on_sale" && !listings.value.some(listing => listing.id === requested.id)) listings.value.unshift(requested);
        if (selectedListingId.value && !selectedListing.value) setNotice("所选货源已无法预约，请重新选择在架货源或收藏等待上架");
      } catch (e) { listings.value = []; }
      finally { loading.value = false; }
    }
    async function load() {
      try {
        book.value = await api("/catalog/books/" + id.value);
        conditions.value = await api("/search/conditions");
        if (store.token) {
          const favs = await api("/search/favorites/mine");
          fav.value = favs.some((f) => f.book_id == id.value);
        }
        await loadListings();
      } catch (e) { loadFailed.value = true; setError(e.message); }
    }
    const { busy, run } = useBusy();
    function toggleFav() {
      if (!store.token) return requestLogin();
      return run(async () => {
        if (fav.value) await api("/search/favorites/" + id.value, { method: "DELETE" });
        else await api("/search/favorites/" + id.value, { method: "POST" });
        fav.value = !fav.value;
        setNotice(fav.value ? "已收藏，有货源将提醒你" : "已取消收藏");
      }).catch((e) => setError(e.message));
    }
    function reserveListing(l) {
      if (!store.token) return requestLogin("book/" + id.value + "?listing=" + l.id);
      return run(async () => {
        await api("/orders", { method: "POST", body: { listing_id: l.id } });
        setNotice("预约成功，等待卖方确认");
        go("orders");
      }).catch((e) => setError(e.message));
    }
    function submitWanted() {
      if (!store.token) return requestLogin();
      return run(async () => {
        const d = await api("/listings/wanted", { method: "POST", body: { book_id: Number(id.value), min_condition: w.min_condition, max_price: w.max_price } });
        setNotice(d.matched ? `求购已发布，命中 ${d.matched} 个货源` : "求购已发布，有货将通知你");
      }).catch((e) => setError(e.message));
    }
    onMounted(load);
    return { book, fav, conditions, listings, loading, coverErr, loadFailed, selectedImage, selectedListingId, selectedListing, ownListing, w, busy, cheapest, isLoggedIn,
             toggleFav, reserveListing, submitWanted, go, openAssistant };
  },
};
