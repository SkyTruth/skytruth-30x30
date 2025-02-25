import { useState } from 'react';

import { MapProvider } from 'react-map-gl';

import type { AppProps } from 'next/app';
import { useRouter } from 'next/router';

import { GoogleTagManager } from '@next/third-parties/google'
import { QueryClient, QueryClientProvider, Hydrate } from '@tanstack/react-query';
import { NextIntlClientProvider } from 'next-intl';

import 'styles/globals.css';
import 'mapbox-gl/dist/mapbox-gl.css';

import Analytics from '@/components/analytics';
import { figtree, overpassMono } from '@/styles/fonts';

export type LayoutProps<PageProps = object, Props = React.ComponentProps<'div'>> = {
  Component?: React.FC<Props>;
  props?: Props | ((props: PageProps) => Props);
};

type Props = AppProps & {
  dehydratedState: unknown;
  Component: {
    layout?: LayoutProps;
  };
};

const App: React.FC<AppProps> = ({ Component, pageProps }: Props) => {
  // Never ever instantiate the client outside a component, hook or callback as it can leak data
  // between users
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } })
  );

  const router = useRouter();
  const GTMID = process.env.NEXT_PUBLIC_GOOGLE_ANALYTICS;

  const Layout = Component?.layout?.Component ?? ((page) => page?.children);

  let layoutProps = {};
  if (Component.layout?.props) {
    if (typeof Component.layout.props === 'function') {
      layoutProps = Component.layout.props(pageProps);
    } else {
      layoutProps = Component.layout.props;
    }
  }

  return (
    <>
      <style jsx global>{`
        :root {
          --font-overpass-mono: ${overpassMono.style.fontFamily};
          --font-figtree: ${figtree.style.fontFamily};
        }
      `}</style>
      <NextIntlClientProvider locale={router.locale} messages={pageProps.messages}>
        <QueryClientProvider client={queryClient}>
          <Hydrate state={pageProps.dehydratedState}>
            <MapProvider>
              <Analytics />
              <Layout {...layoutProps}>
                <Component {...pageProps} />
                <GoogleTagManager gtmId={GTMID} />
              </Layout>
            </MapProvider>
          </Hydrate>
        </QueryClientProvider>
      </NextIntlClientProvider>
    </>
  );
};

export default App;
