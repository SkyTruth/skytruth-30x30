/**
 * Collapses consecutive slashes in ctx.path (e.g. //admin/init → /admin/init).
 *
 * The GCP load balancer rewrites /cms/* → /* by stripping the "/cms/" prefix
 * and prepending "/". If the browser requests /cms//admin/init the rewrite
 * produces //admin/init. The public static route /((?!uploads/).+) matches
 * that path and passes it to koa-static, which calls resolve-path and throws
 * "Malicious Path" because the path starts with "//".
 *
 * This middleware runs first and normalises the path so the admin route
 * /admin/:path* matches correctly.
 */
export default () => async (ctx, next) => {
  if (ctx.path.startsWith('//')) {
    ctx.path = ctx.path.replace(/\/+/g, '/');
  }
  await next();
};
