import { FC, useEffect } from 'react';

import Script from 'next/script';

const Analytics: FC = () => {
  const GAKey = process.env.NEXT_PUBLIC_GOOGLE_ANALYTICS;
  const heapID = process.env.NEXT_PUBLIC_HEAP_ANALYTICS_ID;

  useEffect(() => {
    const scriptBody: Text =
      document.createTextNode(`window.heapReadyCb=window.heapReadyCb||[],window.heap=window.heap||[],heap.load=function(e,t){window.heap.envId=e,window.heap.clientConfig=t=t||{},window.heap.clientConfig.shouldFetchServerConfig=!1;var a=document.createElement("script");a.type="text/javascript",a.async=!0,a.src="https://cdn.us.heap-api.com/config/"+e+"/heap_config.js";var r=document.getElementsByTagName("script")[0];r.parentNode.insertBefore(a,r);var n=["init","startTracking","stopTracking","track","resetIdentity","identify","getSessionId","getUserId","getIdentity","addUserProperties","addEventProperties","removeEventProperty","clearEventProperties","addAccountProperties","addAdapter","addTransformer","addTransformerFn","onReady","addPageviewProperties","removePageviewProperty","clearPageviewProperties","trackPageview"],i=function(e){return function(){var t=Array.prototype.slice.call(arguments,0);window.heapReadyCb.push({name:e,fn:function(){heap[e]&&heap[e].apply(heap,t)}})}};for(var p=0;p<n.length;p++)heap[n[p]]=i(n[p])};
            heap.load("${heapID}");`);
    const script: HTMLScriptElement = document.createElement('script');

    script.type = 'text/javascript';
    script.id = 'heapAnalyticsTag';
    script.append(scriptBody);
    document.head.append(script);
  }, []);

  return (
    <>
      {!!GAKey && (
        <>
          <Script
            id="google-tag-manager"
            src={`https://www.googletagmanager.com/gtag/js?id=${GAKey}`}
          />
          <Script
            id="google-tag-manager-init"
            dangerouslySetInnerHTML={{
              __html: `
                window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('js', new Date()); gtag('config', '${GAKey}');
              `,
            }}
          />
        </>
      )}
    </>
  );
};

export default Analytics;
