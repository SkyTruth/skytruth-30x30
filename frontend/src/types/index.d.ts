import { useTranslations } from 'next-intl';

declare global {
  interface Window {
    // ? As we are using explicitily window to access the `gtag` property we need to declare it before using it
    gtag: UniversalAnalytics.ga;
  }
}

declare module '*.svg';
declare module '*.svg' {
  const content: {
    id: string;
    viewBox: string;
    content: string;
    node: SVGSymbolElement;
  };
  export default content;
}
declare module '*.png';
declare module '*.jpg';

export type FCWithMessages<P = NonNullable<unknown>> = React.FC<P> & {
  messages: Parameters<typeof useTranslations>[0][];
};

export interface ForwadedComponentWithMessages<P = NonNullable<unknown>>
  extends React.ForwardRefExoticComponent<P & RefAttributes<HTMLElement>> {
  messages?: Parameters<typeof useTranslations>[0][];
}

export type SharedMarineAreaCountries = {
  slug: string;
  name: string;
}[];
