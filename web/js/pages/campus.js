const CampusView = {
  template: `
  <div class="container campus-page">
    <div class="breadcrumb"><a href="#/home">首页</a><ui-icon name="chevron" :size="13"/><span>{{ pageTitle }}</span></div>
    <template v-if="page==='news'"><header class="editorial-heading" v-reveal><span class="eyebrow">THE BOOKLOOP JOURNAL / 校园资讯</span><h1>书页之外，<span>校园之内。</span></h1><p>关于好书、关于分享，也关于每一次安心的校园相遇。</p><span class="journal-volume">READ SLOWLY. LIVE FULLY.</span></header><div class="journal-notice"><ui-icon name="book" :size="17"/>书循阅读与交易指南 · 非学校官方新闻发布渠道</div><div class="guide-grid journal-grid"><button class="guide-card" v-for="(guide,index) in guides" :key="guide.title" @click="openArticle(index)"><div class="guide-image"><img :src="'./assets/campus/'+guide.image+'.webp'" :alt="guide.title" loading="lazy"/><span class="guide-index">0{{ index+1 }}</span></div><div><span>{{ guide.label }}</span><h2>{{ guide.title }}</h2><p>{{ guide.summary }}</p><span class="guide-read">阅读全文<ui-icon name="diagonal" :size="17"/></span></div></button></div><div class="campus-photo-note" v-reveal><img src="./assets/campus/bell_tower.webp" alt="校园钟楼" loading="lazy"/><div><span class="eyebrow">SLOW DOWN, READ ON</span><h2>在熟悉的校园，<br/>遇见未读过的世界。</h2><a class="text-link" href="#/market">去寻找下一本好书<ui-icon name="arrow" :size="17"/></a></div></div></template>

    <template v-else-if="page==='activities'"><section class="activity-hero"><img src="./assets/campus/ginkgo_avenue.webp" alt="校园银杏大道"/><div><span class="eyebrow">PASS IT ON · BOOKLOOP</span><h1>把知识留下，<br/>让故事继续。</h1><p>毕业季教材循环计划</p><span>你的旧教材，也许是另一位同学正需要的起点。</span><button class="btn" @click="openDonation">我想捐赠一本书<ui-icon name="arrow" :size="17"/></button></div></section><div class="activity-intro"><div><span class="eyebrow">EVERY BOOK DESERVES ANOTHER CHAPTER</span><h2>让一本书的价值，<br/>不止于一个学期。</h2></div><p>把不再使用的教材整理出来，通过书循提交捐赠申请。审核通过后，由平台协调分配给需要的同学。每一份心意都有记录，每一次知识接力都有来处。</p></div><div class="activity-steps"><article><span>01</span><ui-icon name="book" :size="30"/><h3>整理你的教材</h3><p>核对书名与版次，保留完整可读的教材，如实说明使用情况。</p></article><article><span>02</span><ui-icon name="heart" :size="30"/><h3>提交捐赠申请</h3><p>在教材目录中选择书籍和数量，提交后等待平台审核。</p></article><article><span>03</span><ui-icon name="hands" :size="30"/><h3>完成知识接力</h3><p>审核后按平台安排完成线下交接，把知识留给下一位同学。</p></article></div><section class="card donation-history" v-if="store.token"><div class="section-heading"><h2>我的捐赠申请</h2><button class="text-button" @click="loadDonations">刷新记录<ui-icon name="arrow" :size="15"/></button></div><div v-if="donationLoading" class="spinner">正在读取记录…</div><div class="empty" v-else-if="!donations.length">第一份知识接力，从你开始。</div><div class="source-row" v-for="donation in donations" :key="donation.id"><ui-icon name="book"/><div class="source-owner"><b>{{ donation.book_title }}</b><span>{{ donation.quantity }} 本 · {{ donation.created_at?.slice(0,10) }}</span></div><span class="tag">{{ donation.status==='pending' ? '等待审核' : donation.status==='approved' ? '审核通过' : donation.status==='rejected' ? '未通过' : donation.status }}</span></div></section></template>

    <template v-else><section class="about-hero"><div><span class="eyebrow">A BOOK SHARED, A STORY CONTINUED</span><img src="./assets/bookloop.svg" width="65" height="65" alt="书循标识"/><h1>书有来处，<br/>循有归途。</h1><p>我们相信，一本书被读过以后，<br/>它的故事才刚刚开始。</p></div><img class="about-campus" src="./assets/campus/school_history_museum.webp" alt="成都信息工程大学校史馆"/></section><section class="about-copy"><span class="eyebrow">HELLO, WE ARE BOOKLOOP</span><h2>在成信大，让好书循环起来。</h2><p>书循是面向成都信息工程大学校园的二手教材循环平台，也是一次关于资源共享与绿色校园的工程实践。我们把课程与教材、书与读者连接起来，让闲置教材再次回到课堂。</p><p>从发布到检索，从预约到线下交接，再到信用评价，我们希望把每一次书籍流转做得清楚、安心、有温度。平台提供信息匹配与预约，书款由双方在线下自行结算。</p><div class="about-values"><div><ui-icon name="leaf" :size="27"/><h3>循环</h3><p>让知识多走一程</p></div><div><ui-icon name="shield" :size="27"/><h3>信任</h3><p>让每次交接可追溯</p></div><div><ui-icon name="hands" :size="27"/><h3>连接</h3><p>让同校书友遇见彼此</p></div></div><a class="btn" href="#/market">从一本好书开始<ui-icon name="arrow" :size="17"/></a></section></template>

    <div class="modal-mask" v-if="article" @click.self="article=null"><article class="modal article-modal" role="dialog" aria-modal="true" aria-labelledby="article-title"><button class="icon-button modal-close" aria-label="关闭文章" @click="article=null"><ui-icon name="close"/></button><img :src="'./assets/campus/'+article.image+'.webp'" :alt="article.title"/><span class="eyebrow">书循 · {{ article.label }}</span><h2 id="article-title">{{ article.title }}</h2><p v-for="paragraph in article.paragraphs" :key="paragraph">{{ paragraph }}</p><a class="btn" href="#/market">去集市看看<ui-icon name="arrow" :size="16"/></a></article></div>

    <div class="modal-mask" v-if="donationOpen" @click.self="donationOpen=false"><form class="modal" role="dialog" aria-modal="true" aria-labelledby="donation-title" @submit.prevent="submitDonation"><div class="row"><h2 id="donation-title">让这本书，继续发光</h2><button class="icon-button" type="button" aria-label="关闭捐赠申请" @click="donationOpen=false"><ui-icon name="close"/></button></div><p class="muted">请选择教材目录中的书籍，提交后等待平台审核。</p><label class="field"><span>书名 / 书籍编号</span><input v-model="donationKeyword" @input="searchDonationBooks" placeholder="输入书名或书籍编号检索" required/></label><div class="search-results" v-if="donationBooks.length"><button type="button" v-for="book in donationBooks" :key="book.id" @click="donationBook=book;donationKeyword=book.title;donationBooks=[]">{{ book.title }}<small>{{ book.isbn }}</small></button></div><div class="selected-book-note" v-if="donationBook"><ui-icon name="check" :size="16"/>已选择《{{ donationBook.title }}》</div><label class="field"><span>捐赠数量</span><input type="number" min="1" max="99" step="1" v-model.number="donationQuantity" required/></label><button class="btn full-width" type="submit" :disabled="donationBusy || !donationBook">{{ donationBusy ? '正在提交…' : '提交捐赠申请' }}<ui-icon name="heart" :size="17"/></button><p class="hint">提交申请不代表已完成捐赠，交接安排以审核结果为准。</p></form></div>
  </div>`,
  setup() {
    const page = computed(() => store.route.name);
    const pageTitle = computed(() => ({ news: "校园资讯", activities: "校园活动", about: "关于书循" })[page.value]);
    const article = ref(null);
    const donations = ref([]);
    const donationLoading = ref(false);
    const donationOpen = ref(false);
    const donationKeyword = ref("");
    const donationBook = ref(null);
    const donationBooks = ref([]);
    const donationQuantity = ref(1);
    const donationBusy = ref(false);
    let donationTimer;
    let donationSequence = 0;
    function openArticle(index) { article.value = READING_GUIDES[index] || null; }
    function openDonation() {
      if (!store.token) return requestLogin("activities?donate=1");
      donationOpen.value = true;
    }
    async function loadDonations() {
      if (!store.token) return;
      donationLoading.value = true;
      try { donations.value = await api("/admin/donations"); }
      catch (error) { setError(error.message); }
      finally { donationLoading.value = false; }
    }
    function searchDonationBooks() {
      donationBook.value = null;
      clearTimeout(donationTimer);
      const request = ++donationSequence;
      donationTimer = setTimeout(async () => {
        if (!donationKeyword.value.trim()) { donationBooks.value = []; return; }
        try {
          const result = await api("/catalog/books?size=6&keyword=" + encodeURIComponent(donationKeyword.value.trim()));
          if (request === donationSequence) donationBooks.value = result.items;
        } catch (error) { setError(error.message); }
      }, 250);
    }
    async function submitDonation() {
      if (donationBusy.value || !donationBook.value) return;
      if (!Number.isInteger(donationQuantity.value) || donationQuantity.value < 1 || donationQuantity.value > 99) return setError("请输入 1 到 99 之间的整数数量");
      donationBusy.value = true;
      try {
        await api("/admin/donations", { method: "POST", body: { book_id: donationBook.value.id, quantity: donationQuantity.value } });
        donationOpen.value = false;
        donationBook.value = null;
        donationKeyword.value = "";
        donationQuantity.value = 1;
        setNotice("捐赠申请已提交，谢谢你的知识接力！");
        await loadDonations();
      } catch (error) { setError(error.message); }
      finally { donationBusy.value = false; }
    }
    onMounted(() => {
      if (page.value === "activities") {
        loadDonations();
        if (store.route.params.donate) openDonation();
      }
      if (page.value === "news" && store.route.params.article !== undefined) openArticle(Number(store.route.params.article));
    });
    onUnmounted(() => { clearTimeout(donationTimer); donationSequence++; });
    return { store, page, pageTitle, guides: READING_GUIDES, article, openArticle, donations, donationLoading, donationOpen, donationKeyword, donationBook, donationBooks, donationQuantity, donationBusy, openDonation, loadDonations, searchDonationBooks, submitDonation };
  },
};
