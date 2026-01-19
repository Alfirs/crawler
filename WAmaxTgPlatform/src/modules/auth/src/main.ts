import express from 'express';
import cors from 'cors';
import compression from 'compression';
import 'express-async-errors';

import { logger } from '@/config/logger.config';
import { authRouter } from './controllers/auth.controller';

const app = express();

// Middleware
app.use(compression());
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    service: 'auth',
    timestamp: new Date().toISOString(),
  });
});

// API routes
app.use('/auth', authRouter);

// Error handling
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error(err);
  res.status(err.status || 500).json({
    error: {
      code: err.code || 'INTERNAL_ERROR',
      message: err.message || 'Internal server error',
    },
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: {
      code: 'NOT_FOUND',
      message: 'Endpoint not found',
    },
  });
});

if (process.env.NODE_ENV !== 'test') {
  const port = process.env.PORT || 3004;
  app.listen(port, () => {
    logger.info(`Auth Service started on port ${port}`);
  });
}

export { app };
