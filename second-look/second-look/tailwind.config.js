/** Colors point at CSS variables in src/index.css so SVG and Tailwind share one palette. */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)', s1: 'var(--s1)', s2: 'var(--s2)', ln: 'var(--ln)', tx: 'var(--tx)', mu: 'var(--mu)',
        mem: 'var(--mem)', obs: 'var(--obs)', bad: 'var(--bad)', ok: 'var(--ok)', acc: 'var(--acc)',
      },
      fontFamily: { sans: ['"Schibsted Grotesk"', 'system-ui', '-apple-system', '"Segoe UI"', 'sans-serif'] },
    },
  },
  plugins: [],
}
