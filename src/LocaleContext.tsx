import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  detectLang,
  namedCopy,
  persistLang,
  type Copy,
  type Lang,
} from "./i18n";
import { useData } from "./DataContext";

type LocaleCtx = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Copy;
};

const Ctx = createContext<LocaleCtx | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const { wrapped } = useData();
  const [lang, setLangState] = useState<Lang>(detectLang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (next: Lang) => {
    persistLang(next);
    setLangState(next);
  };

  const names = useMemo(() => {
    const profile = wrapped.profile;
    const fallback = profile.username || "User";
    const dn = profile.displayName;
    return {
      en: dn?.en || fallback,
      ru: dn?.ru || dn?.en || fallback,
      ruGenitive: dn?.ruGenitive || dn?.ru || dn?.en || fallback,
    };
  }, [wrapped.profile]);

  const value = useMemo<LocaleCtx>(
    () => ({
      lang,
      setLang,
      t: namedCopy(lang, names),
    }),
    [lang, names],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLocale() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
