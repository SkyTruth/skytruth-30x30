import { CdnClient } from '@localazy/cdn-client';
import deepmerge from 'deepmerge';
import { pick } from 'lodash-es';
import { useTranslations } from 'next-intl';

export const fetchTranslations = async (
  locale: string,
  pickedMessages?: Parameters<typeof useTranslations>[0][]
) => {
  let mergedMessages;

  const isDefaultLocale = locale === 'en';

  if (process.env.LOCALAZY_CDN?.length > 0) {
    const cdn = await CdnClient.create({
      metafile: process.env.LOCALAZY_CDN,
    });

    const messages = await cdn.fetch({
      files: cdn.metafile.files.find(({ file }) => file !== 'strapi.json'),
      locales: isDefaultLocale ? locale : ['en', locale],
    });

    if (isDefaultLocale) {
      mergedMessages = messages;
    } else {
      // Use the English language as a fallback
      mergedMessages = deepmerge(messages['en'], messages[locale]);
    }
  } else {
    const defaultMessages = (await import(`../../../translations/en.json`)).default;

    if (isDefaultLocale) {
      mergedMessages = defaultMessages;
    } else {
      const messages = (await import(`../../../translations/${locale}.json`)).default;
      // Use the English language as a fallback
      mergedMessages = deepmerge(defaultMessages, messages);
    }
  }

  if (pickedMessages) {
    return pick(mergedMessages, pickedMessages);
  }

  return mergedMessages;
};
