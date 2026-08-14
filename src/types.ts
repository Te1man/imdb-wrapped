export type TitleCard = {
  id?: string | null;
  title: string;
  year?: number | null;
  type?: string;
  poster?: string | null;
  userRating?: number | null;
  imdbRating?: number | null;
  votes?: number | null;
  runtimeMin?: number | null;
  releaseDate?: string | null;
  ratedOn?: string | null;
  series?: string | null;
  season?: number | null;
  episode?: number | null;
  url?: string | null;
};

export type PersonStat = {
  name: string;
  id?: string | null;
  count: number;
  poster?: string | null;
};

export type NamedCount = {
  name: string;
  count: number;
  id?: string | null;
  poster?: string | null;
  year?: number | null;
  avgRating?: number | null;
};

export type HighsAndLows = {
  highestAverage: TitleCard | null;
  lowestAverage: TitleCard | null;
  mostPopular: TitleCard | null;
  mostObscure: TitleCard | null;
  newest: TitleCard | null;
  oldest: TitleCard | null;
  longest: TitleCard | null;
  shortest: TitleCard | null;
};

export type YearStats = {
  year: number | null;
  label: string;
  toDate: boolean;
  count: number;
  hours: number;
  minutes: number;
  avgPerMonth: number;
  avgPerWeek: number;
  avgRating: number | null;
  monthly: number[];
  monthlyPosters: string[][];
  daily: Record<string, number>;
  types: Record<string, number>;
  premieres: number;
  older: number;
  ratingsSpread: Record<string, number>;
  highsAndLows: HighsAndLows;
  highest: TitleCard[];
  lowest: TitleCard[];
  kinderThanAvg: TitleCard[];
  harsherThanAvg: TitleCard[];
  popular: TitleCard[];
  obscure: TitleCard[];
  newest: TitleCard[];
  oldest: TitleCard[];
  longest: TitleCard[];
  shortest: TitleCard[];
  genres: NamedCount[];
  decades: NamedCount[];
  countries: NamedCount[];
  languages: NamedCount[];
  themes: NamedCount[];
  themesRated: NamedCount[];
  keywords: NamedCount[];
  keywordsRated: NamedCount[];
  directors: PersonStat[];
  stars: PersonStat[];
  series: NamedCount[];
  first: TitleCard | null;
  last: TitleCard | null;
  milestones: (TitleCard & { n: number })[];
  mostActiveDay: { date: string; count: number } | null;
  vsImdb: {
    avgUser: number | null;
    avgImdb: number | null;
    delta: number;
    kinder: number;
    harsher: number;
    same: number;
  };
  heroPosters: string[];
};

export type CatalogKind = "all" | "movies" | "series";

export type YearBundle = Record<CatalogKind, YearStats>;

export type WrappedData = {
  profile: {
    username: string;
    userId: string;
    url: string;
    avatar: string;
    totalRatings: number;
    watchlist: number;
    badges: number;
    lists: { name: string; count: number; id: string }[];
    interests: {
      id: string;
      name: string;
      count: number;
      avgRating?: number | null;
      image?: string | null;
      url: string;
    }[];
    favoritePeople: { id: string; name: string; poster?: string | null }[];
    favorites: TitleCard[];
    displayName?: { en: string; ru: string; ruGenitive: string };
    telegram?: string | null;
  };
  generatedAt: string;
  years: number[];
  defaultYear: number;
  allTime: YearBundle;
  byYear: Record<string, YearBundle>;
  coverage: { parsed: number; withPoster: number; withId: number };
};

export type WatchlistItem = {
  id: string;
  title: string;
  originalTitle?: string | null;
  year?: number | null;
  type?: string;
  poster?: string | null;
  imdbRating?: number | null;
  votes?: number | null;
  runtimeMin?: number | null;
  addedOn?: string | null;
  genres?: string[];
  countries?: { id?: string | null; name: string }[];
  directors?: string[];
  url?: string | null;
  releaseDate?: string | null;
  liveNew?: boolean;
};

export type WatchlistData = {
  source: string;
  url: string;
  updatedAt: string;
  count: number;
  addedYears: number[];
  items: WatchlistItem[];
};
