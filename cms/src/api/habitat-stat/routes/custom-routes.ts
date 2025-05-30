export default {
  routes: [
    {
      method: 'POST',
      path: '/habitat-stats/:year',
      handler: 'habitat-stat.bulkUpsert'
    },
  ]
}