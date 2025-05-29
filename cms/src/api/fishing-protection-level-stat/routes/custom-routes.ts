export default {
  routes: [
    {
      method: 'POST',
      path: '/fishing-protection-level-stats',
      handler: 'fishing-protection-level-stat.bulkUpsert'
    },
  ]
}