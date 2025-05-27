export default {
  routes: [
    {
      method: 'POST',
      path: '/protection-coverage-stats/:year',
      handler: 'protection-coverage-stat.bulkUpsert'
    },
  ]
}