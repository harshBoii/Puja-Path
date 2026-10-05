import "./storybook.css";

import type { Preview } from "@storybook/react-vite";
import { useEffect } from "react";

/** A locale toolbar: every story renders in en, hi, ta and te with that locale's real strings and fonts. */
const preview: Preview = {
  globalTypes: {
    locale: {
      description: "Locale",
      toolbar: { title: "Locale", icon: "globe", items: ["en", "hi", "ta", "te"], dynamicTitle: true },
    },
  },
  initialGlobals: { locale: "en" },
  decorators: [
    (Story, ctx) => {
      const locale = ctx.globals.locale as string;
      useEffect(() => { document.documentElement.lang = locale; }, [locale]);
      return <div className="bg-marble-50 p-4 text-ink-900" lang={locale}><Story /></div>;
    },
  ],
  parameters: { layout: "fullscreen", a11y: { test: "error" } },
};
export default preview;
