import { usePathname } from 'next/navigation';
import { useRouter } from 'next/router';

import { useLocale, useTranslations } from 'next-intl';

import { Select, SelectTrigger, SelectContent, SelectItem } from '@/components/ui/select';
// import { useMapSearchParams } from '@/containers/map/content/map/sync-settings';
import { FCWithMessages } from '@/types';

const LanguageSelector: FCWithMessages = () => {
  const t = useTranslations('components.language-selector');
  const locale = useLocale();
  // const searchParams = useMapSearchParams();

  const { push, asPath } = useRouter();
  // const path = usePathname();
  // const currentPage = asPath.split('/')[0];
  // const locationCode = asPath.split('/')[2];
  // console.log('PATH', `${currentPage}/${locationCode.toUpperCase()}?${searchParams.toString()}`)
  return (
    <Select
      value={locale}
      // onValueChange={(newLocale) => console.log(`I'm the path: ${newLocale}${path}?${searchParams.toString()}`)}
      onValueChange={(newLocale) => push(asPath, undefined, { locale: newLocale })}

      // onValueChange={(newLocale) => push(`${newLocale}${basePath}?${searchParams.toString()}`)}
      // onValueChange={(newLocale) => push({ pathname, query: searchParams.toString()}, asPath, { locale: newLocale })}
    >
      <SelectTrigger variant="alternative">
        <span className="sr-only">
          {t('selected-language', {
            language: locale === 'es' ? t('spanish') : locale === 'fr' ? t('french') : t('english'),
          })}
        </span>
        <span className="not-sr-only">{locale.toLocaleUpperCase()}</span>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="en">English{locale !== 'en' && ` (${t('english')})`}</SelectItem>
        <SelectItem value="es">Español{locale !== 'es' && ` (${t('spanish')})`}</SelectItem>
        <SelectItem value="fr">Français{locale !== 'fr' && ` (${t('french')})`}</SelectItem>
      </SelectContent>
    </Select>
  );
};

LanguageSelector.messages = ['components.language-selector'];

export default LanguageSelector;
