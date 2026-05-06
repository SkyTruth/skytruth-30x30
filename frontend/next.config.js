/**
 * @type { import('next').NextConfig }
 */
const nextConfig = {
  // Configure pageExtensions to include md and mdx
  pageExtensions: ['ts', 'tsx', 'js', 'jsx'],
  // ? https://nextjs.org/docs/advanced-features/output-file-tracing#automatically-copying-traced-files
  output: 'standalone',
  poweredByHeader: false,
  webpack(config) {
    config.module.rules.push({
      test: /\.svg$/,
      use: [
        {
          loader: 'svg-sprite-loader',
        },
        {
          loader: 'svgo-loader',
          options: {
            plugins: [
              {
                name: 'preset-default',
                params: {
                  overrides: {
                    convertColors: { shorthex: false },
                    convertPathData: false,
                  },
                },
              },
            ],
          },
        },
      ],
    });

    return config;
  },
  rewrites() {
    return [
      {
        source: '/progress-tracker',
        destination: '/progress-tracker/GLOB',
      },
      {
        source: '/conservation-builder',
        destination: '/conservation-builder/GLOB',
      },
    ];
  },
  redirects() {
    return [
      {
        source: '/',
        destination: '/progress-tracker',
        permanent: true,
      },
      {
        source: '/about',
        destination: 'https://skytruth.org/30x30/why',
        permanent: true,
      },
      {
        source: '/knowledge-hub',
        destination: 'https://skytruth.org/30x30/why',
        permanent: true,
      },
    ];
  },
  i18n: {
    locales: ['en', 'es', 'fr', 'pt'],
    defaultLocale: 'en',
  },
};

module.exports = nextConfig;
