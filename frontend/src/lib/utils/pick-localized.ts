/**
 * Returns the locale-matching variant of a Strapi entity — either the entity
 * itself (if `entity.locale === locale`) or the first matching item in its
 * `localizations` array.
 *
 * Works around Orval types that drop `locale`/`localizations` at deeply
 * nested positions (e.g. when a relation is truncated to `{ id, documentId }`
 * — see https://github.com/strapi/strapi/issues/22808). When the input is a
 * union like `Environment | PaChildrenItemEnvironment`, the return narrows
 * to the variant that actually declares `localizations` (here, `Environment`),
 * giving callers access to `.name`, `.slug`, etc. without casts.
 */
type Localized<T> = T extends unknown
  ? 'localizations' extends keyof T
    ? T
    : never
  : never;

export function pickLocalized<T extends object>(
  entity: T | null | undefined,
  locale: string
): Localized<T> | undefined {
  if (!entity) return undefined;
  const typedEntity = entity as T & {
    locale?: string | null;
    localizations?: Array<T & { locale?: string | null }> | null;
  };
  if (typedEntity.locale === locale) return typedEntity as Localized<T>;
  return typedEntity.localizations?.find((loc) => loc?.locale === locale) as Localized<T> | undefined;
}
