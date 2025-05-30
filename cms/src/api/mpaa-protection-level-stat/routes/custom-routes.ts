export default {
  routes: [
    {
      method: 'POST',
      path: '/mpaa-protection-level-stats',
      handler: 'mpaa-protection-level-stat.bulkUpsert'
    },

  ]
}