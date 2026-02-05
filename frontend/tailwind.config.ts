import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        polymarket: {
          primary: '#00D395',
          secondary: '#7B61FF',
          dark: '#0D1117',
          darker: '#010409',
          card: '#161B22',
          border: '#30363D',
        }
      }
    },
  },
  plugins: [],
}
export default config
