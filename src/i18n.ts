export type Lang = "en" | "ru";

export type LocalizedMedia = {
  title?: string;
  titleRu?: string | null;
  name?: string;
  nameRu?: string | null;
  poster?: string | null;
  posterRu?: string | null;
};

export function mediaTitle(item: LocalizedMedia, lang: Lang): string {
  const en = item.title || item.name || "";
  const ru = item.titleRu || item.nameRu;
  return (lang === "ru" && ru) || en;
}

export function mediaPoster(item: LocalizedMedia, lang: Lang): string | null {
  return ((lang === "ru" && item.posterRu) || item.poster) || null;
}

const STORAGE = "imdbw-lang";

export function detectLang(): Lang {
  try {
    const q = new URLSearchParams(window.location.search).get("lang");
    if (q === "ru" || q === "en") return q;
    const stored = localStorage.getItem(STORAGE);
    if (stored === "ru" || stored === "en") return stored;
  } catch {
    /* ignore */
  }
  const list =
    typeof navigator !== "undefined" && navigator.languages?.length
      ? navigator.languages
      : typeof navigator !== "undefined"
        ? [navigator.language]
        : [];
  for (const code of list) {
    if ((code || "").toLowerCase().startsWith("ru")) return "ru";
  }
  return "en";
}

export function persistLang(lang: Lang) {
  try {
    localStorage.setItem(STORAGE, lang);
    const url = new URL(window.location.href);
    url.searchParams.set("lang", lang);
    window.history.replaceState({}, "", url);
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lang;
}

function pluralRu(n: number, one: string, few: string, many: string) {
  const abs = Math.abs(n);
  if (!Number.isInteger(abs)) return few;
  const n10 = abs % 10;
  const n100 = abs % 100;
  if (n10 === 1 && n100 !== 11) return one;
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return few;
  return many;
}

function enPlural(n: number, one: string, many: string) {
  return Math.abs(n) === 1 ? one : many;
}

export function fmt(n: number, lang: Lang) {
  return n.toLocaleString(lang === "ru" ? "ru-RU" : "en-US");
}

export function formatKindCount(
  formatted: string,
  n: number,
  kind: "all" | "movies" | "series",
  lang: Lang,
) {
  if (lang === "ru") {
    const noun =
      kind === "series"
        ? pluralRu(n, "сериал", "сериала", "сериалов")
        : kind === "movies"
          ? pluralRu(n, "фильм", "фильма", "фильмов")
          : pluralRu(n, "картина", "картины", "картин");
    return `${formatted} ${noun}`;
  }
  const noun =
    kind === "series"
      ? enPlural(n, "series", "series")
      : kind === "movies"
        ? enPlural(n, "film", "films")
        : enPlural(n, "title", "titles");
  return `${formatted} ${noun}`;
}

export const MONTHS: Record<Lang, string[]> = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  ru: ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
};

function parseIsoDate(iso: string | null | undefined) {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(iso: string | null | undefined, lang: Lang) {
  const d = parseIsoDate(iso);
  if (!d) return iso || "";
  return `${d.getDate()} ${MONTHS[lang][d.getMonth()]} ${d.getFullYear()}`;
}

export function formatDateLong(iso: string | null | undefined, lang: Lang) {
  return formatDate(iso, lang);
}

export function formatDateShort(iso: string | null | undefined, lang: Lang) {
  const d = parseIsoDate(iso);
  if (!d) return iso || "";
  return `${d.getDate()} ${MONTHS[lang][d.getMonth()]}`;
}

export const WEEKDAYS: Record<Lang, string[]> = {
  en: ["M", "T", "W", "T", "F", "S", "S"],
  ru: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
};

export const WEEKDAYS_FULL: Record<Lang, string[]> = {
  en: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
  ru: ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
};

export const WEEKDAYS_WHEN: Record<Lang, string[]> = {
  en: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
  ru: ["в понедельник", "во вторник", "в среду", "в четверг", "в пятницу", "в субботу", "в воскресенье"],
};

const TYPE: Record<Lang, Record<string, string>> = {
  en: {
    movie: "Movies",
    tvEpisode: "TV episodes",
    tvSeries: "TV series",
    tvMiniSeries: "Mini series",
    tvMovie: "TV movies",
    tvSpecial: "TV specials",
    tvShort: "TV shorts",
    short: "Shorts",
    video: "Videos",
    videoGame: "Games",
    podcastEpisode: "Podcasts",
  },
  ru: {
    movie: "Фильмы",
    tvEpisode: "Серии",
    tvSeries: "Сериалы",
    tvMiniSeries: "Мини-сериалы",
    tvMovie: "ТВ-фильмы",
    tvSpecial: "ТВ-спецвыпуски",
    tvShort: "ТВ-шорты",
    short: "Шорты",
    video: "Видео",
    videoGame: "Игры",
    podcastEpisode: "Подкасты",
  },
};

const TYPE_RU: Record<string, [string, string, string]> = {
  movie: ["фильм", "фильма", "фильмов"],
  tvEpisode: ["серия", "серии", "серий"],
  tvSeries: ["сериал", "сериала", "сериалов"],
  tvMiniSeries: ["мини-сериал", "мини-сериала", "мини-сериалов"],
  tvMovie: ["ТВ-фильм", "ТВ-фильма", "ТВ-фильмов"],
  tvSpecial: ["ТВ-спецвыпуск", "ТВ-спецвыпуска", "ТВ-спецвыпусков"],
  tvShort: ["ТВ-шорт", "ТВ-шорта", "ТВ-шортов"],
  short: ["шорт", "шорта", "шортов"],
  video: ["видео", "видео", "видео"],
  videoGame: ["игра", "игры", "игр"],
  podcastEpisode: ["подкаст", "подкаста", "подкастов"],
};

const GENRE: Record<string, string> = {
  Action: "Боевик",
  Adventure: "Приключения",
  Animation: "Анимация",
  Biography: "Биография",
  Comedy: "Комедия",
  Crime: "Криминал",
  Documentary: "Документальный",
  Drama: "Драма",
  Family: "Семейный",
  Fantasy: "Фэнтези",
  "Film-Noir": "Нуар",
  "Game-Show": "Игровое шоу",
  History: "История",
  Horror: "Ужасы",
  Music: "Музыка",
  Musical: "Мюзикл",
  Mystery: "Детектив",
  News: "Новости",
  "Reality-TV": "Реалити",
  Romance: "Мелодрама",
  "Sci-Fi": "Фантастика",
  Short: "Короткий метр",
  Sport: "Спорт",
  "Talk-Show": "Ток-шоу",
  Thriller: "Триллер",
  War: "Война",
  Western: "Вестерн",
};

const COUNTRY: Record<string, string> = {
  "United States": "США",
  "United Kingdom": "Великобритания",
  France: "Франция",
  Germany: "Германия",
  Japan: "Япония",
  "South Korea": "Южная Корея",
  Russia: "Россия",
  Italy: "Италия",
  Spain: "Испания",
  Canada: "Канада",
  Australia: "Австралия",
  India: "Индия",
  China: "Китай",
  Sweden: "Швеция",
  Denmark: "Дания",
  Norway: "Норвегия",
  Finland: "Финляндия",
  Poland: "Польша",
  Brazil: "Бразилия",
  Mexico: "Мексика",
  Iran: "Иран",
  Turkey: "Турция",
  "Hong Kong": "Гонконг",
  Taiwan: "Тайвань",
  Belgium: "Бельгия",
  Netherlands: "Нидерланды",
  Ireland: "Ирландия",
  "New Zealand": "Новая Зеландия",
  "Czech Republic": "Чехия",
  Austria: "Австрия",
  Switzerland: "Швейцария",
  Hungary: "Венгрия",
  Ukraine: "Украина",
  Argentina: "Аргентина",
  Chile: "Чили",
  "South Africa": "ЮАР",
  Israel: "Израиль",
  Greece: "Греция",
  Portugal: "Португалия",
  Romania: "Румыния",
  Serbia: "Сербия",
  Croatia: "Хорватия",
  Iceland: "Исландия",
  Thailand: "Таиланд",
  Indonesia: "Индонезия",
  Singapore: "Сингапур",
  Philippines: "Филиппины",
  "United Arab Emirates": "ОАЭ",
  Egypt: "Египет",
  Morocco: "Марокко",
  Colombia: "Колумбия",
  Estonia: "Эстония",
  Latvia: "Латвия",
  Lithuania: "Литва",
  Georgia: "Грузия",
  Kazakhstan: "Казахстан",
  Belarus: "Беларусь",
  Luxembourg: "Люксембург",
  Bulgaria: "Болгария",
  Malta: "Мальта",
  Jordan: "Иордания",
  Moldova: "Молдова",
  Cambodia: "Камбоджа",
  Vietnam: "Вьетнам",
  Qatar: "Катар",
  Peru: "Перу",
  "Dominican Republic": "Доминикана",
  Pakistan: "Пакистан",
  Iraq: "Ирак",
  Malaysia: "Малайзия",
  "Puerto Rico": "Пуэрто-Рико",
  Bahamas: "Багамы",
  Armenia: "Армения",
  Tunisia: "Тунис",
  Monaco: "Монако",
  "Costa Rica": "Коста-Рика",
  Cameroon: "Камерун",
  "North Korea": "КНДР",
  Yemen: "Йемен",
  "Saudi Arabia": "Саудовская Аравия",
  Montenegro: "Черногория",
  Bangladesh: "Бангладеш",
  Guadeloupe: "Гваделупа",
  Kenya: "Кения",
  Liechtenstein: "Лихтенштейн",
  Fiji: "Фиджи",
  Jamaica: "Ямайка",
  Aruba: "Аруба",
  Slovakia: "Словакия",
  Nepal: "Непал",
  Cyprus: "Кипр",
  Bahrain: "Бахрейн",
  Slovenia: "Словения",
  Macao: "Макао",
  Venezuela: "Венесуэла",
  Zambia: "Замбия",
  Bermuda: "Бермуды",
  "Cayman Islands": "Каймановы острова",
  "Soviet Union": "СССР",
  "West Germany": "ФРГ",
  Yugoslavia: "Югославия",
  Czechoslovakia: "Чехословакия",
  "Serbia and Montenegro": "Сербия и Черногория",
  "Federal Republic of Yugoslavia": "СРЮ",
};

const LANGUAGE: Record<string, string> = {
  English: "Английский",
  French: "Французский",
  Spanish: "Испанский",
  German: "Немецкий",
  Italian: "Итальянский",
  Russian: "Русский",
  Japanese: "Японский",
  Chinese: "Китайский",
  Mandarin: "Мандарин",
  Cantonese: "Кантонский",
  Korean: "Корейский",
  Portuguese: "Португальский",
  Hindi: "Хинди",
  Arabic: "Арабский",
  Swedish: "Шведский",
  Danish: "Датский",
  Norwegian: "Норвежский",
  Finnish: "Финский",
  Dutch: "Нидерландский",
  Polish: "Польский",
  Turkish: "Турецкий",
  Czech: "Чешский",
  Hungarian: "Венгерский",
  Greek: "Греческий",
  Hebrew: "Иврит",
  Thai: "Тайский",
  Indonesian: "Индонезийский",
  Ukrainian: "Украинский",
  Romanian: "Румынский",
  Persian: "Персидский",
  Latin: "Латынь",
  Yiddish: "Идиш",
  Catalan: "Каталанский",
  Basque: "Баскский",
  Galician: "Галисийский",
  Welsh: "Валлийский",
  Irish: "Ирландский",
  Icelandic: "Исландский",
  Croatian: "Хорватский",
  Serbian: "Сербский",
  Bosnian: "Боснийский",
  Bulgarian: "Болгарский",
  Slovak: "Словацкий",
  Slovenian: "Словенский",
  Estonian: "Эстонский",
  Latvian: "Латышский",
  Lithuanian: "Литовский",
  Georgian: "Грузинский",
  Armenian: "Армянский",
  Azerbaijani: "Азербайджанский",
  Kazakh: "Казахский",
  Vietnamese: "Вьетнамский",
  Tagalog: "Тагальский",
  Filipino: "Филиппинский",
  Malay: "Малайский",
  Tamil: "Тамильский",
  Telugu: "Телугу",
  Malayalam: "Малаялам",
  Kannada: "Каннада",
  Bengali: "Бенгальский",
  Urdu: "Урду",
  Punjabi: "Пенджаби",
  Marathi: "Маратхи",
  Gujarati: "Гуджарати",
  Sinhala: "Сингальский",
  Afrikaans: "Африкаанс",
  Swahili: "Суахили",
  Hawaiian: "Гавайский",
  Mongolian: "Монгольский",
  Romany: "Цыганский",
  "Sign Languages": "Жестовые языки",
  "American Sign Language": "Амслен",
  "British Sign Language": "Британский жестовый",
  "German Sign Language": "Немецкий жестовый",
  None: "Без диалогов",
};

const LIST_NAME: Record<string, string> = {
  "My favorite movies": "Мои любимые фильмы",
};

export function typeLabel(id: string, lang: Lang, n?: number) {
  if (lang === "ru" && n != null) {
    const forms = TYPE_RU[id];
    if (forms) return pluralRu(n, ...forms);
  }
  return TYPE[lang][id] || id;
}

export function genreName(name: string, lang: Lang) {
  if (lang !== "ru") return name;
  return GENRE[name] || name;
}

export function countryName(name: string, lang: Lang) {
  if (lang !== "ru") return name;
  return COUNTRY[name] || name;
}

export function languageName(name: string, lang: Lang) {
  if (lang !== "ru") return name;
  return LANGUAGE[name] || name;
}

export function listName(name: string, lang: Lang) {
  if (lang !== "ru") return name;
  return LIST_NAME[name] || name;
}

export { tagName } from "./i18nTags";

export function decadeName(name: string, lang: Lang) {
  if (lang !== "ru") return name;
  return name.replace(/s$/, "е");
}

export type Copy = {
  allTime: string;
  toDate: string;
  displayName: string;
  yearToDate: string;
  yearToDateMovies: string;
  yearToDateSeries: string;
  yearInFilm: string;
  yearInMovies: string;
  yearInSeries: string;
  yearAllTime: string;
  yearAllTimeMovies: string;
  yearAllTimeSeries: string;
  kindLabel: string;
  kindAll: string;
  kindMovies: string;
  kindSeries: string;
  wrapped: string;
  activityView: string;
  last12Months: string;
  ratedThisYear: string;
  ratedByYear: string;
  monthlyBars: string;
  heatCalendar: string;
  less: string;
  more: string;
  mon: string;
  wed: string;
  fri: string;
  titlesRated: (n: number) => string;
  hours: (n: number) => string;
  averageRating: string;
  avgPerMonth: (n: string) => string;
  avgPerWeek: (n: string) => string;
  byWeekday: string;
  byWeekdayHint: (day: string, formatted: string, n: number) => string;
  weekdayTip: (formatted: string, n: number, kind: "all" | "movies" | "series") => string;
  titlesByKind: (formatted: string, n: number, kind: "all" | "movies" | "series") => string;
  hoursHint1: string;
  hoursHint1Movies: string;
  hoursHint1Series: string;
  avgRuntime: (hours: number, minutes: number) => string;
  avgHint1: string;
  avgHint2: (formatted: string, n: number, year?: string) => string;
  heroRated: (formatted: string, n: number) => string;
  heroHours: (formatted: string, hours: number) => string;
  newThisYear: string;
  premieres: (count: number, year: number | null) => string;
  olderTitles: (n: number) => string;
  movies: (n: number) => string;
  moviesSlice: (n: number) => string;
  tvEpisodes: (n: number) => string;
  series: (n: number) => string;
  pictures: (n: number) => string;
  other: (n: number) => string;
  vsImdb: string;
  kinder: string;
  harsher: string;
  same: string;
  ratingsSpread: string;
  watchlist: string;
  watchlistAll: (formatted: string, n: number) => string;
  watchlistEmpty: (year: string) => string;
  watchlistYear: (year: string) => string;
  watchlistFull: string;
  inWatchlist: string;
  added: string;
  addedIn: (year: string) => string;
  firstRated: (kind: "all" | "movies" | "series") => string;
  mostRecent: (kind: "all" | "movies" | "series") => string;
  milestones: string;
  ratingMilestones: string;
  ordinal: (n: number) => string;
  mostActiveDay: string;
  titlesOn: (n: number, date: string) => string;
  highest: string;
  highestAverage: string;
  lowestAverage: string;
  highsAndLows: string;
  bestOf: (year: string) => string;
  worstOf: (year: string) => string;
  bestOfItems: (n: number, kind: "all" | "movies" | "series") => string;
  lowest: string;
  ratedHigher: string;
  ratedLower: string;
  mostPopular: string;
  mostPopularOne: string;
  mostObscure: string;
  newest: string;
  oldest: string;
  longest: string;
  shortest: string;
  votes: (formatted: string, n: number) => string;
  minutes: (n: number) => string;
  minutesLong: (n: number) => string;
  mostRatedSeries: string;
  episodesRated: (n: number) => string;
  directors: string;
  stars: string;
  peopleTitles: (n: number) => string;
  genres: string;
  themesKeywords: string;
  themes: string;
  keywords: string;
  mostWatched: string;
  byRating: string;
  decades: string;
  countries: string;
  countriesN: (n: number) => string;
  worldMap: string;
  mapAttribution: string;
  languages: string;
  titleTypes: string;
  onProfile: string;
  interests: string;
  stillToWatch: string;
  yetToSee: (name: string, kind: "all" | "movies" | "series") => string;
  watchlistAddedIn: (year: string) => string;
  allTimeRatings: (kind: "all" | "movies" | "series") => string;
  badges: (n: number) => string;
  collections: (n: number) => string;
  favoriteTitles: string;
  favoritePeople: string;
  footerCredit: string;
  heatTitle: (date: string, n: number) => string;
  language: string;
  share: string;
  shareCopied: string;
  shareText: (name: string, year: string) => string;
};

export const copy: Record<Lang, Copy> = {
  en: {
    allTime: "All time",
    toDate: "to date",
    displayName: "User",
    yearToDate: "User’s year to date",
    yearToDateMovies: "User’s year in movies to date",
    yearToDateSeries: "User’s year in series to date",
    yearInFilm: "User’s year in film",
    yearInMovies: "User’s year in movies",
    yearInSeries: "User’s year in series",
    yearAllTime: "User’s all time",
    yearAllTimeMovies: "User’s films, all time",
    yearAllTimeSeries: "User’s series, all time",
    kindLabel: "Catalog",
    kindAll: "All",
    kindMovies: "Movies",
    kindSeries: "Series",
    wrapped: "Wrapped",
    activityView: "Activity view",
    last12Months: "Last 12 months",
    ratedThisYear: "Rated this year",
    ratedByYear: "Rated by year",
    monthlyBars: "Monthly bars",
    heatCalendar: "Contribution calendar",
    less: "Less",
    more: "More",
    mon: "Mon",
    wed: "Wed",
    fri: "Fri",
    titlesRated: (n) => enPlural(n, "Title rated", "Titles rated"),
    hours: (n) => enPlural(n, "Hour", "Hours"),
    averageRating: "Average rating",
    avgPerMonth: (n) => `${n} average per month`,
    avgPerWeek: (n) => `${n} average per week`,
    byWeekday: "By day of week",
    byWeekdayHint: (day, formatted, n) =>
      `Most on ${day} — ${formatted} ${enPlural(n, "rating", "ratings")}`,
    weekdayTip: (formatted, n, kind) => formatKindCount(formatted, n, kind, "en"),
    titlesByKind: (formatted, n, kind) => formatKindCount(formatted, n, kind, "en"),
    hoursHint1: "Runtime of movies and series",
    hoursHint1Movies: "Runtime of all movies",
    hoursHint1Series: "Runtime of all episodes",
    avgRuntime: (h, m) =>
      h > 0 ? `${h}h ${m}m average runtime` : `${m} min average runtime`,
    avgHint1: "On IMDb’s 1–10 scale",
    avgHint2: (formatted, n, year) =>
      year
        ? `${formatted} ${enPlural(n, "rating", "ratings")} in ${year}`
        : `${formatted} ${enPlural(n, "rating", "ratings")} all-time`,
    heroRated: (formatted, n) => `${formatted} ${enPlural(n, "title rated", "titles rated")}`,
    heroHours: (h, n) => `${h} ${enPlural(Math.round(n), "hour", "hours")}`,
    newThisYear: "new this year",
    premieres: (count, year) =>
      year ? `${enPlural(count, "premiere", "premieres")} ${year}` : "Rated the year they came out",
    olderTitles: (n) => enPlural(n, "Older title", "Older titles"),
    movies: (n) => enPlural(n, "movie", "movies"),
    moviesSlice: (n) => enPlural(n, "Movie", "Movies"),
    tvEpisodes: (n) => enPlural(n, "TV episode", "TV episodes"),
    series: (n) => enPlural(n, "Series", "Series"),
    pictures: (n) => enPlural(n, "title", "titles"),
    other: (n) => enPlural(n, "Other", "Other"),
    vsImdb: "vs IMDb",
    kinder: "Kinder than IMDb",
    harsher: "Harsher",
    same: "Same",
    ratingsSpread: "Ratings spread",
    watchlist: "Watchlist",
    watchlistAll: (formatted, n) =>
      `${formatted} ${enPlural(n, "title", "titles")} still to watch. Open a year to see what you added then, or see the full list on `,
    watchlistEmpty: (year) => `Nothing added to the watchlist in ${year}. The full queue is on `,
    watchlistYear: (year) => `Added in ${year}.`,
    watchlistFull: "Full watchlist on IMDb",
    inWatchlist: "In watchlist",
    added: "added",
    addedIn: (year) => `Added in ${year}`,
    firstRated: (kind) =>
      kind === "series" ? "First series" : kind === "movies" ? "First film" : "First picture",
    mostRecent: (kind) =>
      kind === "series" ? "Last series" : kind === "movies" ? "Last film" : "Last picture",
    milestones: "Milestones",
    ratingMilestones: "Rating milestones",
    ordinal: (n) => {
      const v = n % 100;
      let suf = "th";
      if (v < 11 || v > 13) {
        if (n % 10 === 1) suf = "st";
        else if (n % 10 === 2) suf = "nd";
        else if (n % 10 === 3) suf = "rd";
      }
      return `${n}${suf}`.toUpperCase();
    },
    mostActiveDay: "Most active day",
    titlesOn: (n, date) => `${n.toLocaleString("en-US")} titles on ${date}`,
    highest: "Highest rated",
    highestAverage: "Highest average",
    lowestAverage: "Lowest average",
    highsAndLows: "Highs and lows",
    bestOf: (year) => `Best of ${year}`,
    worstOf: (year) => `Worst of ${year}`,
    bestOfItems: (n, kind) =>
      kind === "series"
        ? `${n} ${enPlural(n, "series", "series")}`
        : `${n} ${enPlural(n, "film", "films")}`,
    lowest: "Lowest rated",
    ratedHigher: "Rated higher than average",
    ratedLower: "Rated lower than average",
    mostPopular: "Most popular",
    mostPopularOne: "Most popular on IMDb",
    mostObscure: "Most obscure",
    newest: "Newest",
    oldest: "Oldest",
    longest: "Longest",
    shortest: "Shortest",
    votes: (formatted, n) => `${formatted} ${enPlural(n, "vote", "votes")}`,
    minutes: (n) => `${n} min`,
    minutesLong: (n) => `${n} ${enPlural(n, "minute", "minutes")}`,
    mostRatedSeries: "Most-rated series",
    episodesRated: (n) => `${n} episodes rated`,
    directors: "Most-rated directors",
    stars: "Most-rated stars",
    peopleTitles: (n) => `${n} titles`,
    genres: "Genres",
    themesKeywords: "Themes & keywords",
    themes: "Themes",
    keywords: "Keywords",
    mostWatched: "Most watched",
    byRating: "Average score",
    decades: "Decades",
    countries: "Countries",
    countriesN: (n) => `${n} ${enPlural(n, "country", "countries")}`,
    worldMap: "World map",
    mapAttribution: "Map data from Natural Earth",
    languages: "Languages",
    titleTypes: "Title types",
    onProfile: "On this IMDb profile",
    interests: "Interests",
    stillToWatch: "Watchlist",
    yetToSee: (name, kind) =>
      kind === "series"
        ? `Highly rated series ${name} is yet to see`
        : `Highly rated films ${name} is yet to see`,
    watchlistAddedIn: (year) => `Watchlist added in ${year}`,
    allTimeRatings: (kind) =>
      kind === "series" ? "Series ratings" : kind === "movies" ? "Movie ratings" : "All ratings",
    badges: (n) => enPlural(n, "Badge", "Badges"),
    collections: (n) => enPlural(n, "Collection", "Collections"),
    favoriteTitles: "Favorite titles",
    favoritePeople: "Favorite people",
    footerCredit: "Built from public IMDb ratings for ",
    heatTitle: (date, n) => `${date}: ${n} ${n === 1 ? "title" : "titles"}`,
    language: "Language",
    share: "Share",
    shareCopied: "Link copied",
    shareText: (name, year) =>
      year === "all" ? `${name} · IMDb Wrapped` : `${name} · ${year} · IMDb Wrapped`,
  },
  ru: {
    allTime: "За всё время",
    toDate: "на сегодня",
    displayName: "Пользователь",
    yearToDate: "год пользователя на сегодня",
    yearToDateMovies: "год пользователя в фильмах на сегодня",
    yearToDateSeries: "год пользователя в сериалах на сегодня",
    yearInFilm: "год пользователя в кино",
    yearInMovies: "год пользователя в фильмах",
    yearInSeries: "год пользователя в сериалах",
    yearAllTime: "пользователь за всё время",
    yearAllTimeMovies: "фильмы пользователя за всё время",
    yearAllTimeSeries: "сериалы пользователя за всё время",
    kindLabel: "Каталог",
    kindAll: "Всё вместе",
    kindMovies: "Фильмы",
    kindSeries: "Сериалы",
    wrapped: "Wrapped",
    activityView: "Вид активности",
    last12Months: "Последние 12 месяцев",
    ratedThisYear: "Оценки за год",
    ratedByYear: "Оценки по годам",
    monthlyBars: "Столбики по месяцам",
    heatCalendar: "Календарь как на GitHub",
    less: "Меньше",
    more: "Больше",
    mon: "Пн",
    wed: "Ср",
    fri: "Пт",
    titlesRated: (n) => pluralRu(n, "оценка", "оценки", "оценок"),
    hours: (n) => pluralRu(n, "час", "часа", "часов"),
    averageRating: "Средняя оценка",
    avgPerMonth: (n) => `${n} в среднем за месяц`,
    avgPerWeek: (n) => `${n} в среднем за неделю`,
    byWeekday: "По дням недели",
    byWeekdayHint: (day, formatted, n) =>
      `Чаще всего ${day} — ${formatted} ${pluralRu(n, "оценка", "оценки", "оценок")}`,
    weekdayTip: (formatted, n, kind) => formatKindCount(formatted, n, kind, "ru"),
    titlesByKind: (formatted, n, kind) => formatKindCount(formatted, n, kind, "ru"),
    hoursHint1: "Хронометраж фильмов и сериалов",
    hoursHint1Movies: "Хронометраж всех фильмов",
    hoursHint1Series: "Хронометраж всех серий",
    avgRuntime: (h, m) =>
      h > 0 ? `${h} ч ${m} мин в среднем` : `${m} мин в среднем`,
    avgHint1: "Шкала IMDb от 1 до 10",
    avgHint2: (formatted, n, year) =>
      year
        ? `${formatted} ${pluralRu(n, "оценка", "оценки", "оценок")} в ${year}`
        : `${formatted} ${pluralRu(n, "оценка", "оценки", "оценок")} за всё время`,
    heroRated: (formatted, n) => `${formatted} ${pluralRu(n, "оценка", "оценки", "оценок")}`,
    heroHours: (h, n) =>
      `${h} ${n < 100 && !Number.isInteger(n) ? "часов" : pluralRu(Math.round(n), "час", "часа", "часов")}`,
    newThisYear: "новинки",
    premieres: (count, year) =>
      year
        ? `${pluralRu(count, "премьера", "премьеры", "премьер")} ${year}`
        : "Оценены в год выхода",
    olderTitles: (n) => pluralRu(n, "старая картина", "старые картины", "старых картин"),
    movies: (n) => pluralRu(n, "фильм", "фильма", "фильмов"),
    moviesSlice: (n) => pluralRu(n, "фильм", "фильма", "фильмов"),
    tvEpisodes: (n) => pluralRu(n, "серия", "серии", "серий"),
    series: (n) => pluralRu(n, "сериал", "сериала", "сериалов"),
    pictures: (n) => pluralRu(n, "картина", "картины", "картин"),
    other: (n) => pluralRu(n, "другое", "других", "других"),
    vsImdb: "против IMDb",
    kinder: "Выше IMDb",
    harsher: "Ниже IMDb",
    same: "Как у IMDb",
    ratingsSpread: "Распределение оценок",
    watchlist: "Буду смотреть",
    watchlistAll: (formatted, n) =>
      `${formatted} ${pluralRu(n, "картина", "картины", "картин")} ещё не смотрел. Открой год, чтобы увидеть, что добавил тогда, или весь список на `,
    watchlistEmpty: (year) => `В ${year} в список «буду смотреть» ничего не добавлял. Полная очередь на `,
    watchlistYear: (year) => `Добавлено в ${year}.`,
    watchlistFull: "Весь список на IMDb",
    inWatchlist: "В списке «буду смотреть»",
    added: "добавлено",
    addedIn: (year) => `Добавлено в ${year}`,
    firstRated: (kind) =>
      kind === "series" ? "Первый сериал" : kind === "movies" ? "Первый фильм" : "Первая картина",
    mostRecent: (kind) =>
      kind === "series" ? "Последний сериал" : kind === "movies" ? "Последний фильм" : "Последняя картина",
    milestones: "Рубежи",
    ratingMilestones: "Рубежи оценок",
    ordinal: (n) => `${n}-й`,
    mostActiveDay: "Самый активный день",
    titlesOn: (n, date) =>
      `${n.toLocaleString("ru-RU")} ${pluralRu(n, "картина", "картины", "картин")} · ${date}`,
    highest: "Самые высокие оценки",
    highestAverage: "Высший рейтинг IMDb",
    lowestAverage: "Низший рейтинг IMDb",
    highsAndLows: "Высокое и низкое",
    bestOf: (year) => `Лучшее за ${year}`,
    worstOf: (year) => `Худшие за ${year}`,
    bestOfItems: (n, kind) =>
      kind === "series"
        ? `${n} ${pluralRu(n, "сериал", "сериала", "сериалов")}`
        : `${n} ${pluralRu(n, "фильм", "фильма", "фильмов")}`,
    lowest: "Самые низкие оценки",
    ratedHigher: "Оценка выше средней",
    ratedLower: "Оценка ниже средней",
    mostPopular: "Самые популярные",
    mostPopularOne: "Популярное на IMDb",
    mostObscure: "Самые малоизвестные",
    newest: "Самые новые",
    oldest: "Самые старые",
    longest: "Самые длинные",
    shortest: "Самые короткие",
    votes: (formatted, n) => `${formatted} ${pluralRu(n, "голос", "голоса", "голосов")}`,
    minutes: (n) => `${n} мин`,
    minutesLong: (n) => `${n} ${pluralRu(n, "минута", "минуты", "минут")}`,
    mostRatedSeries: "Сериалы с наибольшим числом оценок",
    episodesRated: (n) =>
      `${n} ${pluralRu(n, "серия оценена", "серии оценены", "серий оценено")}`,
    directors: "Режиссёры",
    stars: "Актёры",
    peopleTitles: (n) => `${n} ${pluralRu(n, "картина", "картины", "картин")}`,
    genres: "Жанры",
    themesKeywords: "Темы и ключевые слова",
    themes: "Темы",
    keywords: "Ключевые слова",
    mostWatched: "Чаще всего",
    byRating: "Средний балл",
    decades: "Десятилетия",
    countries: "Страны",
    countriesN: (n) => `${n} ${pluralRu(n, "страна", "страны", "стран")}`,
    worldMap: "Карта мира",
    mapAttribution: "Карта: Natural Earth",
    languages: "Языки",
    titleTypes: "Типы картин",
    onProfile: "На этом профиле IMDb",
    interests: "Интересы",
    stillToWatch: "Вотчлист",
    yetToSee: (name, kind) =>
      kind === "series"
        ? `Высоко оценённые сериалы, которые ${name} ещё не смотрел`
        : `Высоко оценённые картины, которые ${name} ещё не смотрел`,
    watchlistAddedIn: (year) => `В список в ${year}`,
    allTimeRatings: (kind) =>
      kind === "series" ? "Оценки сериалов" : kind === "movies" ? "Оценки фильмов" : "Все оценки",
    badges: (n) => pluralRu(n, "бейдж", "бейджа", "бейджей"),
    collections: (n) => pluralRu(n, "коллекция", "коллекции", "коллекций"),
    favoriteTitles: "Любимые картины",
    favoritePeople: "Любимые персоны",
    footerCredit: "Собрано по публичным оценкам IMDb пользователя ",
    heatTitle: (date, n) =>
      `${date}: ${n} ${pluralRu(n, "картина", "картины", "картин")}`,
    language: "Язык",
    share: "Поделиться",
    shareCopied: "Ссылка скопирована",
    shareText: (name, year) =>
      year === "all" ? `${name} · IMDb Wrapped` : `${name} · ${year} · IMDb Wrapped`,
  },
};

export type DisplayNames = { en: string; ru: string; ruGenitive: string };

function enPossessive(name: string) {
  return /s$/i.test(name) ? `${name}’` : `${name}’s`;
}

export function namedCopy(lang: Lang, names: DisplayNames): Copy {
  const base = copy[lang];
  if (lang === "en") {
    const poss = enPossessive(names.en);
    return {
      ...base,
      displayName: names.en,
      yearToDate: `${poss} year to date`,
      yearToDateMovies: `${poss} year in movies to date`,
      yearToDateSeries: `${poss} year in series to date`,
      yearInFilm: `${poss} year in film`,
      yearInMovies: `${poss} year in movies`,
      yearInSeries: `${poss} year in series`,
      yearAllTime: `${poss} all time`,
      yearAllTimeMovies: `${poss} films, all time`,
      yearAllTimeSeries: `${poss} series, all time`,
    };
  }
  const ru = names.ru;
  const gen = names.ruGenitive;
  return {
    ...base,
    displayName: ru,
    yearToDate: `год ${gen} на сегодня`,
    yearToDateMovies: `год ${gen} в фильмах на сегодня`,
    yearToDateSeries: `год ${gen} в сериалах на сегодня`,
    yearInFilm: `год ${gen} в кино`,
    yearInMovies: `год ${gen} в фильмах`,
    yearInSeries: `год ${gen} в сериалах`,
    yearAllTime: `${ru} за всё время`,
    yearAllTimeMovies: `фильмы ${gen} за всё время`,
    yearAllTimeSeries: `сериалы ${gen} за всё время`,
  };
}
