/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}", "../shared/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // BlockKind colour palette — used for bbox overlays + tree labels
        kind: {
          heading: "#2563eb",       // blue
          paragraph: "#64748b",     // slate
          caption: "#a855f7",       // purple
          formula: "#dc2626",       // red
          figure: "#16a34a",        // green
          table: "#ea580c",         // orange
          list_item: "#0891b2",     // cyan
          list: "#0891b2",
          footnote: "#7c3aed",      // violet
          header: "#94a3b8",        // grey
          footer: "#94a3b8",
          page_number: "#94a3b8",
          reference: "#facc15",     // yellow
          bibitem: "#facc15",
          code: "#475569",
          unknown: "#9ca3af",
        },
      },
    },
  },
  plugins: [],
};
