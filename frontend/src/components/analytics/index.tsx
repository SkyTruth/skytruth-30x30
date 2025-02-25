import { FC } from 'react';

import Script from 'next/script';

type AnalyticsProps = {
  isBody?: boolean;
};

const Analytics: FC = ({ isBody = false }: AnalyticsProps) => {
  const GTMID = process.env.NEXT_PUBLIC_GOOGLE_ANALYTICS;
  const heapID = process.env.NEXT_PUBLIC_HEAP_ANALYTICS_ID;

  if (isBody) {
    return (
      <noscript
        dangerouslySetInnerHTML={{
          __html: `<iframe src="https://www.googletagmanager.com/ns.html?id=${process.env.NEXT_PUBLIC_GOOGLE_ANALYTICS}" height="0" width="0" style="display: none; visibility: hidden;" />`,
        }}
      />
    );
  }

  return (
    <>
      {!!GTMID && (
        <>
          <Script id="gtm" strategy="afterInteractive">
            {`
        (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
        new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
        j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
        'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
        })(window,document,'script','dataLayer','${GTMID}');
      `}
          </Script>
        </>
      )}
      {!!heapID && (
        <Script id="heap-analytics-tag" type="text/javascript">
          {`window.heapReadyCb=window.heapReadyCb||[],window.heap=window.heap||[],heap.load=function(e,t){window.heap.envId=e,window.heap.clientConfig=t=t||{},window.heap.clientConfig.shouldFetchServerConfig=!1;var a=document.createElement("script");a.type="text/javascript",a.async=!0,a.src="https://cdn.us.heap-api.com/config/"+e+"/heap_config.js";var r=document.getElementsByTagName("script")[0];r.parentNode.insertBefore(a,r);var n=["init","startTracking","stopTracking","track","resetIdentity","identify","getSessionId","getUserId","getIdentity","addUserProperties","addEventProperties","removeEventProperty","clearEventProperties","addAccountProperties","addAdapter","addTransformer","addTransformerFn","onReady","addPageviewProperties","removePageviewProperty","clearPageviewProperties","trackPageview"],i=function(e){return function(){var t=Array.prototype.slice.call(arguments,0);window.heapReadyCb.push({name:e,fn:function(){heap[e]&&heap[e].apply(heap,t)}})}};for(var p=0;p<n.length;p++)heap[n[p]]=i(n[p])};
        heap.load("${heapID}");`}
        </Script>
      )}
    </>
  );
};

export default Analytics;
