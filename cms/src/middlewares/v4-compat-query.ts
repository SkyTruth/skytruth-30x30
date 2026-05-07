/**
 * Middleware that restores Strapi v4 comma-separated query param behavior
 * for populate, fields, and sort — only when the Strapi-Response-Format: v4
 * header is present. This allows existing consumers to migrate incrementally.
 */
export default () => {
  return async (ctx, next) => {
    const responseFormat = ctx.request.headers['strapi-response-format'];
    if (responseFormat !== 'v4') {
      return next();
    }

    const query = { ...ctx.query };
    let modified = false;

    for (const key of ['populate', 'fields', 'sort']) {
      if (typeof query[key] === 'string' && query[key].includes(',')) {
        query[key] = query[key].split(',').map((s) => s.trim());
        modified = true;
      }
    }

    if (modified) {
      ctx.query = query;
    }

    return next();
  };
};
