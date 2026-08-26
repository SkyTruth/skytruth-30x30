import { useRouter } from 'next/router';

import { useLocale, useTranslations } from 'next-intl';

import { Select, SelectTrigger, SelectContent, SelectItem } from '@/components/ui/select';
import { FCWithMessages } from '@/types';

const LanguageSelector: FCWithMessages = () => {
  const t = useTranslations('components.language-selector');
  const locale = useLocale();

  const { push, asPath, pathname, query } = useRouter();

  const getLanguageName = () => {
    switch (locale) {
      case 'es':
        return t('spanish');
      case 'fr':
        return t('french');
      case 'pt':
        return t('portuguese');
      case 'id':
        return t('indonesian');
      case 'sw':
        return t('swahili');
      default:
        return t('english');
    }
  };

  return (
    <Select
      value={locale}
      onValueChange={(newLocale) => push({ pathname, query }, asPath, { locale: newLocale })}
    >
      <SelectTrigger variant="alternative">
        <span className="sr-only">
          {t('selected-language', {
            language: getLanguageName(),
          })}
        </span>
        <span className="not-sr-only">{locale.toLocaleUpperCase()}</span>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="en">English{locale !== 'en' && ` (${t('english')})`}</SelectItem>
        <SelectItem value="es">Español{locale !== 'es' && ` (${t('spanish')})`}</SelectItem>
        <SelectItem value="fr">Français{locale !== 'fr' && ` (${t('french')})`}</SelectItem>
        <SelectItem value="pt">Português{locale !== 'pt' && ` (${t('portuguese')})`}</SelectItem>
        <SelectItem value="id">
          Bahasa Indonesia{locale !== 'id' && ` (${t('indonesian')})`}
        </SelectItem>
        <SelectItem value="sw">Kiswahili{locale !== 'sw' && ` (${t('swahili')})`}</SelectItem>
      </SelectContent>
    </Select>
  );
};

LanguageSelector.messages = ['components.language-selector'];

export default LanguageSelector;
