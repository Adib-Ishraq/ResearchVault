/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:             "var(--c-bg)",
        surface:        "var(--c-surface)",
        "surface-subtle":"var(--c-surface-subtle)",
        "surface-raised":"var(--c-surface-raised)",
        text:           "var(--c-text)",
        muted:          "var(--c-muted)",
        accent:         "var(--c-accent)",
        "accent-dark":  "var(--c-accent-dark)",
        "accent-light": "var(--c-accent-light)",
        "accent-muted": "var(--c-accent-muted)",
        border:         "var(--c-border)",
        danger:         "var(--c-danger)",
      },
      fontFamily: {
        sans: ["DM Sans", "Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card:        "0 1px 3px 0 rgb(0 0 0 / 0.07), 0 1px 2px -1px rgb(0 0 0 / 0.05)",
        "card-hover":"0 6px 20px 0 rgb(0 0 0 / 0.10), 0 2px 6px -2px rgb(0 0 0 / 0.07)",
        nav:         "0 1px 0 0 rgb(0 0 0 / 0.06)",
        "btn-accent":"0 3px 8px 0 rgb(74 155 142 / 0.35)",
      },
      keyframes: {
        "fade-up": {
          "0%":   { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease-out both",
        "fade-in": "fade-in 0.25s ease-out both",
      },
    },
  },
  plugins: [],
};
