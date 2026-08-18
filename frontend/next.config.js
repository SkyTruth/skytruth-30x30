/**
 * @type { import('next').NextConfig }
 */
const nextConfig = {
  // Configure pageExtensions to include md and mdx
  pageExtensions: ['ts', 'tsx', 'js', 'jsx'],
  // ? https://nextjs.org/docs/advanced-features/output-file-tracing#automatically-copying-traced-files
  output: 'standalone',
  poweredByHeader: false,
  experimental: {
    // Next 14's file tracer resolves the `default` export condition, but Node >=20.19
    // resolves `module-sync` instead, so these files are required at runtime yet never
    // traced into the standalone bundle. Remove once on a Next version whose tracer
    // understands `module-sync` Can potentially remove with upgrade to Next15.
    outputFileTracingIncludes: {
      '*': [
        './node_modules/async-function/require.mjs',
        './node_modules/async-generator-function/require.mjs',
        './node_modules/generator-function/require.mjs',
      ],
    },
  },
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
    locales: ['en', 'es', 'fr', 'pt', 'id', 'sw'],
    defaultLocale: 'en',
  },
};

module.exports = nextConfig;
