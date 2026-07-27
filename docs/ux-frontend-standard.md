# UX Frontend Standard

Dieser Repository-Pointer verweist auf den verbindlichen Standard aus
[`ha-platform/control#58`](https://gitlab.b-struck.de/ha-platform/control/-/work_items/58)
und das zugehörige
[`0001-ux-frontend-standard.md`](https://gitlab.b-struck.de/ha-platform/control/-/blob/main/docs/adr/0001-ux-frontend-standard.md).

Für den Core-Contracts-Slice gelten daraus insbesondere:

- Svelte 5 mit Vite und TypeScript;
- Bits UI als headless Grundlage, eigene Komponenten-/Styleschicht und
  Tailwind-Tokenintegration;
- Lucide-Icons, Graphite Dark und semantische CSS Custom Properties;
- statische SPA ohne SSR, CDN, Remote-Fonts oder Frontend-Secrets;
- typed read-only REST-/WebSocket-Grenzen, wobei dieser Slice die fünf
  bestehenden Home-Assistant-WebSocket-Kommandos verwendet;
- Shell, Tokens und Basiskomponenten getrennt vom Core-Contracts-
  Fachadapter;
- deutsche Primärbeschriftung, touch-fähige Ziele ab 44 px und sichtbare
  Verbindungs-/Degradierungszustände.

Die konkrete Umsetzung und der Installations-/Rollback-Ablauf stehen in
[`ux-implementation.md`](ux-implementation.md). Eine Umbrella UX, ein
zentrales Gateway und ein fleet-weites Frontend-Refactoring sind nicht Teil
dieses Repository-Slices.
