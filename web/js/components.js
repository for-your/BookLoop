const ICON_PATHS = {
  book: '<path d="M3 4c4-1 6 0 9 2 3-2 5-3 9-2v15c-4-1-6 0-9 2-3-2-5-3-9-2V4Z"/><path d="M12 6v15M6 8l3 1M6 12l3 1M15 9l3-1M15 13l3-1"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
  pin: '<path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4M12 2V1"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 22v-2a8 8 0 0 1 16 0v2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  leaf: '<path d="M20 3C8 2 2 8 6 16c8 4 14-2 14-13Z"/><path d="M3 21 16 8"/>',
  cap: '<path d="m2 8 10-5 10 5-10 5L2 8Z"/><path d="M6 10v7c4 3 8 3 12 0v-7M22 8v8"/>',
  hands: '<path d="m2 8 4-4 5 3 3-2 8 5-5 9-4 1-8-6-3-6Z"/><path d="m6 4 5 3-4 5 3 2 5-4 5 4M12 15l4 4M9 17l3 3"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
  shield: '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  filter: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
  camera: '<path d="M3 6h4l2-3h6l2 3h4v15H3V6Z"/><circle cx="12" cy="13" r="4"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M3 16v5h18v-5"/>',
  message: '<path d="M21 3H3v14h5l4 4 4-4h5V3Z"/><path d="M7 8h10M7 12h7"/>',
  home: '<path d="m2 11 10-9 10 9M5 9v13h14V9M10 22v-8h4v8"/>',
  order: '<rect x="5" y="3" width="14" height="19" rx="2"/><path d="M9 3V1h6v2M9 8h6M9 12h6M9 16h4"/>',
  star: '<path d="m12 2 3 6.5 7 1-5 5 1 7-6-3.5L6 21l1-6.5-5-5 7-1L12 2Z"/>',
  logout: '<path d="M10 3H3v18h7M8 12h14m-5-5 5 5-5 5"/>',
  spark: '<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  play: '<path d="m8 4 12 8-12 8V4Z"/>',
  diagonal: '<path d="M5 19 19 5M5 5h14v14"/>',
};

const UiIcon = {
  props: { name: { type: String, default: "book" }, size: { type: [Number, String], default: 20 } },
  computed: { paths() { return ICON_PATHS[this.name] || ICON_PATHS.book; } },
  template: '<svg class="ui-icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" v-html="paths"></svg>',
};

const BookCover = {
  props: { title: { type: String, default: "等你翻开的一本书" }, src: { type: String, default: "" }, fallbackSrc: { type: String, default: "" }, edition: { type: String, default: "" }, caption: { type: String, default: "" } },
  data() { return { failed: [], squareCover: false }; },
  watch: { src() { this.failed = []; this.squareCover = false; }, fallbackSrc() { this.failed = []; this.squareCover = false; } },
  computed: {
    activeSource() { return [this.src, this.fallbackSrc].find(source => source && !this.failed.includes(source)) || ""; },
    sourceCaption() { return this.activeSource ? (this.activeSource === this.src ? this.caption : "教材目录封面") : "暂无可用封面"; },
  },
  template: `
    <div class="book-jacket" :class="{'no-cover': !activeSource}">
      <img v-if="activeSource" :src="activeSource" :class="{'catalog-cover': squareCover && activeSource.startsWith('/static/covers/')}" :alt="title + ' · ' + (sourceCaption || '书籍封面')" loading="lazy" @load="squareCover = Math.abs($event.target.naturalWidth / $event.target.naturalHeight - 1) < 0.05" @error="failed.push(activeSource)" />
      <div v-else class="cover-missing" role="img" :aria-label="title + '，封面待补充'">
        <ui-icon name="book" :size="30"/><span>封面待补充</span><small>{{ title }}</small>
      </div>
      <span v-if="caption" class="cover-caption">{{ sourceCaption }}</span>
    </div>`,
};

const ReadingCard = {
  props: { item: { type: Object, required: true } },
  emits: ["discover"],
  template: `
    <article class="book-card reading-card motion-card" v-spotlight :data-book-number="item.isbn">
      <button class="book-card-visual" v-tilt @click="$emit('discover',item)" :aria-label="'查看教材：'+item.title"><span class="book-stage-label">THE CAMPUS SHELF</span><book-cover :title="item.title" :src="item.cover"/><span class="book-stage-number">No. {{ item.isbn.slice(-3) }}</span></button>
      <div class="book-card-content"><span class="reading-category">{{ item.category_name }}</span><button class="book-card-title" @click="$emit('discover',item)">{{ item.title }}</button><p class="reading-edition">编号 {{ item.isbn }}<br/>{{ item.edition || '版次以实物为准' }}</p><button class="reading-discover" @click="$emit('discover',item)">{{ item.on_sale_count ? '查看 '+item.on_sale_count+' 个在架货源' : '查看教材 · 收藏求购' }}<ui-icon name="arrow" :size="15"/></button></div>
    </article>`,
};

const BookCard = {
  props: { item: { type: Object, required: true }, saved: Boolean, busy: Boolean },
  emits: ["open", "favorite"],
  template: `
    <article class="book-card motion-card" v-spotlight>
      <button class="book-card-visual" v-tilt @click="$emit('open', item)" :aria-label="'查看' + item.book_title">
        <book-cover :title="item.book_title" :src="item.images?.[0] || item.cover || ''" :fallback-src="item.cover || ''" />
        <span class="condition-stamp">{{ item.condition_level }}</span>
      </button>
      <button class="save-book" :class="{saved}" :aria-label="(saved ? '取消收藏' : '收藏') + item.book_title" :aria-pressed="saved" :disabled="busy" @click="$emit('favorite', item)"><ui-icon name="heart" :size="18" /></button>
      <div class="book-card-content">
        <button class="book-card-title" @click="$emit('open', item)">{{ item.book_title }}</button>
        <div class="book-card-price"><strong><small>¥</small>{{ fmtPrice(item.price) }}</strong><del v-if="item.original_price > item.price">¥{{ fmtPrice(item.original_price) }}</del><span v-if="item.negotiable">可议价</span></div>
        <p class="book-card-location"><ui-icon name="pin" :size="13" />{{ item.point_name || '校内交接' }}</p>
        <div class="book-card-seller"><span class="mini-avatar">{{ (item.seller_name || '同学').slice(-2, -1) || '书' }}</span><span>{{ item.seller_name || '书循同学' }}</span><span class="seller-dot"></span><span>校内书友</span></div>
      </div>
    </article>`,
};
