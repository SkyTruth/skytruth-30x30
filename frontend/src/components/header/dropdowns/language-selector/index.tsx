import { useRouter } from 'next/router';

import { useLocale, useTranslations } from 'next-intl';

import { Select, SelectTrigger, SelectContent, SelectItem } from '@/components/ui/select';
import { FCWithMessages } from '@/types';

const LanguageSelector: FCWithMessages = () => {
  const t = useTranslations('components.language-selector');
  const locale = useLocale();

  const { push, asPath, pathname, query } = useRouter();

  return (
    <Select
      value={locale}
      onValueChange={(newLocale) => push({ pathname, query }, asPath, { locale: newLocale })}
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
        <SelectItem value="pt">Português{locale !== 'pt' && ` (${t('portuguese')})`}</SelectItem>
      </SelectContent>
    </Select>
  );
};

LanguageSelector.messages = ['components.language-selector'];

export default LanguageSelector;
