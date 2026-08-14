import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  detectLang,
  namedCopy,
  persistLang,
  type Copy,
  type Lang,
} from "./i18n";
import type { WrappedData } from "./types";
import data from "./data/stats.json";

type LocaleCtx = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Copy;
};

const Ctx = createContext<LocaleCtx | null>(null);

function displayNames() {
  const profile = (data as WrappedData).profile;
  const fallback = profile.username || "User";
  const names = profile.displayName;
  return {
    en: names?.en || fallback,
    ru: names?.ru || names?.en || fallback,
    ruGenitive: names?.ruGenitive || names?.ru || names?.en || fallback,
  };
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectLang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (next: Lang) => {
    persistLang(next);
    setLangState(next);
  };

  const value = useMemo<LocaleCtx>(
    () => ({
      lang,
      setLang,
      t: namedCopy(lang, displayNames()),
    }),
    [lang],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLocale() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
