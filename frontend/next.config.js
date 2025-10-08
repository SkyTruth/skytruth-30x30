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
  i18n: {
    locales: ['en', 'es', 'fr', 'pt_BR'],
    defaultLocale: 'en',
  },
};

module.exports = nextConfig;
