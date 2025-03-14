import { useMemo } from 'react';

import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';

import { VariantProps, cva } from 'class-variance-authority';
import { Menu } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import ActiveLink from '@/components/active-link';
import Icon from '@/components/ui/icon';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import LanguageSelector from '@/components/header/dropdowns/language-selector';
import Contact from "@/components/header/dropdowns/contact";
import { PAGES } from '@/constants/pages';
import {
  useSyncMapLayerSettings,
  useSyncMapLayers,
  useSyncMapSettings,
} from '@/containers/map/content/map/sync-settings';
import { cn } from '@/lib/classnames';
import ArrowRight from '@/styles/icons/arrow-right.svg';
import { FCWithMessages } from '@/types';

const headerVariants = cva('', {
  variants: {
    theme: {
      normal: 'border border-black bg-white text-black',
      dark: 'border-white bg-black text-white',
    },
  },
  defaultVariants: {
    theme: 'normal',
  },
});

const buttonVariants = cva('', {
  variants: {
    theme: {
      normal: 'ring-offset-white hover:bg-gray-50 focus-visible:ring-black',
      dark: 'ring-offset-black hover:bg-gray-50 focus-visible:ring-white',
    },
  },
  defaultVariants: {
    theme: 'normal',
  },
});

export type HeaderProps = VariantProps<typeof headerVariants> & {
  hideLogo?: boolean;
};

const Header: FCWithMessages<HeaderProps> = ({ theme, hideLogo = false }) => {
  const t = useTranslations('components.header');
  const locale = useLocale();
  
  const navigationItems = useMemo(
    () => [
      {
        name: t('progress-tracker'),
        href: PAGES.progressTracker,
        colorClassName: 'text-orange',
        preserveMapParams: true,
      },
      {
        name: t('conservation-builder'),
        href: PAGES.conservationBuilder,
        colorClassName: 'text-blue',
        preserveMapParams: true,
      },
      { name: t('knowledge-hub'), href: PAGES.knowledgeHub, colorClassName: 'text-green' },
      { name: t('about'), href: PAGES.about, colorClassName: 'text-violet' },
    ],
    [t]
  );

  const contactOptions = useMemo(
    () => [
      { name: t('contact'), href: PAGES.contact },
      { name: t('language'), href: PAGES.language },
    ],
    [t]
  );

  const [mapSettings] = useSyncMapSettings();
  const [mapLayers] = useSyncMapLayers();
  const [mapLayerSettings] = useSyncMapLayerSettings();
  const { query } = useRouter();
  const { locationCode = 'GLOB' } = query;

  const navigationEntries = useMemo(() => {
    return navigationItems.map(({ name, href, colorClassName, preserveMapParams }) => {
      return {
        name: name,
        href: {
          pathname: href,
          ...(preserveMapParams && {
            query: {
              location: locationCode,
              mapParams: JSON.stringify({
                settings: mapSettings,
                layers: mapLayers,
                layerSettings: mapLayerSettings,
              }),
            },
          }),
        },
        ...(preserveMapParams && {
          as: href,
        }),
        colorClassName: colorClassName,
      };
    });
  }, [navigationItems, locationCode, mapSettings, mapLayers, mapLayerSettings]);

  // const languageSelector = (
  //   <Select
  //     value={locale}
  //     onValueChange={(newLocale) => push({ pathname, query }, asPath, { locale: newLocale })}
  //   >
  //     <SelectTrigger variant="alternative">
  //       <span className="sr-only">
  //         {t('selected-language', {
  //           language: locale === 'es' ? t('spanish') : locale === 'fr' ? t('french') : t('english'),
  //         })}
  //       </span>
  //       <span className="not-sr-only">{locale.toLocaleUpperCase()}</span>
  //     </SelectTrigger>
  //     <SelectContent>
  //       <SelectItem value="en">English{locale !== 'en' && ` (${t('english')})`}</SelectItem>
  //       <SelectItem value="es">Español{locale !== 'es' && ` (${t('spanish')})`}</SelectItem>
  //       <SelectItem value="fr">Français{locale !== 'fr' && ` (${t('french')})`}</SelectItem>
  //     </SelectContent>
  //   </Select>
  // );

  // const ContactDropdown = (
  //   <Select
  //     value={locale}
  //     onValueChange={(newLocale) => push({ pathname, query }, asPath, { locale: newLocale })}
  //   >
  //     <SelectTrigger variant="alternative">
  //       <span>{t('contact')}</span>
  //     </SelectTrigger>
  //     <SelectContent>
  //       <SelectItem value="en">English{locale !== 'en' && ` (${t('english')})`}</SelectItem>
  //       <SelectItem value="es">Español{locale !== 'es' && ` (${t('spanish')})`}</SelectItem>
  //       <SelectItem value="fr">Français{locale !== 'fr' && ` (${t('french')})`}</SelectItem>
  //     </SelectContent>
  //   </Select>
  // );

  return (
    <header className={cn('border-b font-mono text-sm', headerVariants({ theme }))}>
      <nav
        className="mx-auto flex items-center justify-between p-6 py-2.5 md:py-3 lg:px-10"
        aria-label={t('global')}
      >
        <span className="flex">
          {!hideLogo && (
            <Link
              href="/"
              className="-my-1.5 inline-block ring-offset-black transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2"
            >
              <Image
                src="/images/skytruth-30-30-logo.svg"
                alt="SkyTruth 30x30"
                width={25}
                height={25}
              />
            </Link>
          )}
        </span>

        {/* Mobile hamburger menu */}
        <div className="flex md:hidden">
          <Sheet>
            <SheetTrigger className="px-3 py-2 ring-offset-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2">
              <span className="sr-only">{t('open-main-menu')}</span>
              <Menu className="h-6 w-6" aria-hidden="true" />
            </SheetTrigger>
            <SheetContent closeLabel={t('close')}>
              <SheetHeader>
                <SheetTitle className="sr-only">{t('main-menu')}</SheetTitle>
                <SheetDescription>
                  <div className="mt-6 flow-root">
                    <div className="-my-6 divide-y divide-gray-500/10">
                      <div className="space-y-2 py-6 font-mono text-sm">
                        {navigationEntries.map(({ name, href, as, colorClassName }) => (
                          <ActiveLink
                            key={name}
                            href={href}
                            as={as}
                            className={cn(
                              'group -mx-3 block px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
                              buttonVariants({ theme })
                            )}
                            activeClassName="is-active"
                          >
                            <Icon
                              icon={ArrowRight}
                              className={cn(
                                'mr-2.5 hidden w-5 fill-black group-[.is-active]:inline-block',
                                colorClassName
                              )}
                            />
                            {name}
                          </ActiveLink>
                        ))}
                        <div className="-mx-3"><LanguageSelector /></div>
                      </div>
                    </div>
                  </div>
                </SheetDescription>
              </SheetHeader>
            </SheetContent>
          </Sheet>
        </div>

        <ul className="hidden md:flex md:gap-x-10">
          {navigationEntries.map(({ name, href, as, colorClassName }) => (
            <li key={name}>
              <ActiveLink
                href={href}
                as={as}
                className="group -mx-3 flex px-3 py-2 ring-offset-white transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2"
                activeClassName="bg-white text-black hover:bg-white is-active"
              >
                <Icon
                  icon={ArrowRight}
                  className={cn(
                    '-mt-1 mr-2.5 hidden w-5 fill-black group-[.is-active]:inline-block',
                    colorClassName
                  )}
                />
                {name}
              </ActiveLink>
            </li>
          ))}
          <li><Contact /></li>
          <li><LanguageSelector /></li>
        </ul>
      </nav>
    </header>
  );
};

Header.messages = ['components.header', ...LanguageSelector.messages];

export default Header;
