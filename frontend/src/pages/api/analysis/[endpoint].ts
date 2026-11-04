import axios, { isAxiosError } from 'axios';
import type { NextApiRequest, NextApiResponse } from 'next';

// cb_api endpoints the frontend may reach through this route
const ENDPOINTS = new Set(['coverage']);

// Just under the frontend's Cloud Run timeout; a slow analysis ends in a 504
const TIMEOUT_MS = 590_000;

export const config = {
  api: {
    // Uploaded shapes can exceed Next's 1mb default; match Cloud Run's 32mb request limit
    bodyParser: { sizeLimit: '32mb' },
  },
};

// Forward a POST to cb_api and return its status and body
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { endpoint } = req.query;
  if (typeof endpoint !== 'string' || !ENDPOINTS.has(endpoint)) {
    return res.status(404).json({ error: 'Not found' });
  }

  const baseUrl = process.env.CB_API_URL;
  if (!baseUrl) {
    console.error('CB_API_URL is not set');
    return res.status(500).json({ error: 'Internal server error' });
  }

  try {
    // cb_api redirects /coverage/ to its public root
    const response = await axios.post(`${baseUrl.replace(/\/+$/, '')}/${endpoint}`, req.body, {
      timeout: TIMEOUT_MS,
      responseType: 'text',
      transformResponse: (data) => data,
      validateStatus: () => true,
    });

    const contentType = response.headers['content-type'];
    if (typeof contentType === 'string') {
      res.setHeader('Content-Type', contentType);
    }
    return res.status(response.status).send(response.data);
  } catch (error) {
    if (isAxiosError(error) && ['ECONNABORTED', 'ETIMEDOUT'].includes(error.code)) {
      console.error(`cb_api /${endpoint} timed out`, error.message);
      return res.status(504).json({ error: 'Analysis timed out' });
    }
    console.error(`cb_api /${endpoint} could not be reached`, error);
    return res.status(502).json({ error: 'Analysis service unavailable' });
  }
}
