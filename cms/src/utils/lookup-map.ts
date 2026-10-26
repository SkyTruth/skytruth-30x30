export type LookupIdField = 'documentId' | 'id';

export type LookupMap<F extends LookupIdField> = {
  [key: string]: F extends 'id' ? number : string;
};

/**
 * Maps a lookup value (slug or code) to an identifier of its row. Localized content types are
 * pinned to the English row so a numeric `id` always points at one locale.
 */
export const getLookupMap = async <F extends LookupIdField>(
  uid: string,
  keyField: string,
  idField: F,
  isLocalized: boolean
): Promise<LookupMap<F>> => {
  const rows = await strapi.db.query(uid as any).findMany({
    select: [idField, keyField],
    where: isLocalized ? { locale: 'en' } : {},
  });

  const lookupMap = {} as LookupMap<F>;
  rows.forEach((row) => {
    lookupMap[row[keyField]] = row[idField];
  });
  return lookupMap;
};
